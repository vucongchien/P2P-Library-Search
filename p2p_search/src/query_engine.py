"""
QueryEngine — Thực hiện AND query trên mạng Chord DHT.

Trace system: Đọc routing trace THẬT từ response.data["routing_trace"],
KHÔNG reconstruct từ message_log. Mỗi hop trong trace được ghi bởi chính node
thực hiện quyết định routing.
"""

from typing import List, Set, Dict
from src.chord.ring import ChordRing
from src.chord.utils import deterministic_hash
from src.models import KeywordLookup, HopEvent, QueryResult, ExecutionStatus, ResultStatus
from src.models import RoutingTrace, RoutingHop
from src.preprocessing import clean_text, tokenize

class QueryEngine:
    def __init__(self, ring: ChordRing):
        self.ring = ring
        
    def query_and(self, initiator_id: int, raw_query: str) -> QueryResult:
        """
        Thực hiện tìm kiếm giao hoán theo chuẩn Incremental Fetch + Early Stop.
        
        Trace chính xác 100%: đọc từ routing response, không suy đoán.
        """
        # 1. Tiền xử lý truy vấn đồng bộ với chiều ghi
        cleaned_query = clean_text(raw_query, "")
        keywords = tokenize(cleaned_query)
        
        if not keywords:
            return QueryResult(
                query=raw_query,
                execution_status=ExecutionStatus.FAILED,
                result_status=ResultStatus.EMPTY,
                total_hops=0,
                initiator_peer=initiator_id,
                final_result=[],
                warnings=["Query is empty or contains only stopwords."],
                trace=[]
            )
            
        try:
            initiator_node = self.ring.get_node(initiator_id)
        except (ValueError, TypeError):
            return QueryResult(
                query=raw_query,
                execution_status=ExecutionStatus.FAILED,
                result_status=ResultStatus.EMPTY,
                total_hops=0,
                initiator_peer=initiator_id,
                final_result=[],
                warnings=[f"Initiator node {initiator_id} does not exist."],
                trace=[]
            )
        
        if initiator_node is None:
            return QueryResult(
                query=raw_query,
                execution_status=ExecutionStatus.FAILED,
                result_status=ResultStatus.EMPTY,
                total_hops=0,
                initiator_peer=initiator_id,
                final_result=[],
                warnings=[f"Initiator node {initiator_id} does not exist."],
                trace=[]
            )
        
        # Ghi nhận vị trí log trước query để tính total_messages chính xác
        start_log_idx = len(self.ring.transport.message_log)
        
        final_doc_ids: Set[int] = set()
        trace_list: List[KeywordLookup] = []
        warnings: List[str] = []
        flags: Dict[str, bool] = {"early_stop": False, "partial_data": False}
        is_first_keyword = True
        
        for k in keywords:
            # --- FETCH qua mạng ---
            api_response = initiator_node.get(k)
            
            # --- LẤY TRACE THẬT từ response ---
            routing_trace_dict = api_response.data.get("routing_trace", {}) if api_response.data else {}
            routing_trace = RoutingTrace.from_dict(routing_trace_dict) if routing_trace_dict else None
            
            # Xử lý phân biệt rỗng do Không Tồn Tại hay rỗng do Mạng Chết
            if not api_response.success:
                warnings.append(f"Network/Routing failed for keyword: '{k}'. Error: {api_response.error}")
                flags["partial_data"] = True
                current_doc_ids = set()
            else:
                current_doc_ids = set(api_response.data.get("doc_ids", []))
            
            # --- XÂY DỰNG HopEvent từ trace thật ---
            hops = []
            target_peer = None
            
            if routing_trace and routing_trace.path:
                for i, rt_hop in enumerate(routing_trace.path):
                    hops.append(HopEvent(
                        hop_number=i + 1,
                        from_node=rt_hop.node_id,
                        to_node=rt_hop.next_node if rt_hop.next_node is not None else routing_trace.target_id,
                        reason=f"[{rt_hop.action}] {rt_hop.reason}"
                    ))
                target_peer = routing_trace.target_id
            
            kw_lookup = KeywordLookup(
                keyword=k,
                hash_value=deterministic_hash(k, initiator_node.m),
                responsible_peer=target_peer,
                posting_list=list(current_doc_ids),
                hops=routing_trace.hop_count if routing_trace else 0,
                routing_path=hops
            )
            trace_list.append(kw_lookup)
            
            # --- INCREMENTAL INTERSECT & EARLY STOP ---
            if is_first_keyword:
                final_doc_ids = current_doc_ids
                is_first_keyword = False
            else:
                final_doc_ids = final_doc_ids.intersection(current_doc_ids)
                
            # Ngắt mạch sớm nếu giao thành tập rỗng
            if not final_doc_ids:
                flags["early_stop"] = True
                warnings.append(f"Early stop triggered after keyword '{k}' because intersection resulted in empty set.")
                break
                
        # Tổng hợp state
        if flags["partial_data"] and not trace_list:
            exec_status = ExecutionStatus.FAILED
        elif flags["partial_data"]:
            exec_status = ExecutionStatus.PARTIAL
        else:
            exec_status = ExecutionStatus.SUCCESS
            
        res_status = ResultStatus.HAS_RESULT if final_doc_ids else ResultStatus.EMPTY
        
        # Total messages = messages thực tế qua transport trong khoảng query này
        total_messages = len(self.ring.transport.message_log) - start_log_idx
        # Total hops = tổng routing hops thật từ trace
        total_hops = sum(kl.hops for kl in trace_list)
        
        return QueryResult(
            query=raw_query,
            execution_status=exec_status,
            result_status=res_status,
            total_hops=total_hops,
            initiator_peer=initiator_id,
            final_result=list(final_doc_ids),
            flags=flags,
            warnings=warnings,
            trace=trace_list
        )

    @staticmethod
    def format_query_trace(result: QueryResult) -> str:
        """
        Format readable cho query trace — dùng trong test/debug (ASCII only).
        """
        sep = "=" * 55
        lines = [
            sep,
            f'  Query: "{result.query}" | Initiator: N{result.initiator_peer}',
            f'  Status: {result.execution_status.value} | Result: {result.result_status.value}',
            sep,
        ]
        
        running_intersection = None
        
        for idx, lookup in enumerate(result.trace):
            lines.append(f'  Keyword: "{lookup.keyword}" (hash={lookup.hash_value})')
            
            for i, hop in enumerate(lookup.routing_path):
                is_last_hop = (i == len(lookup.routing_path) - 1)
                prefix = "  \\-" if is_last_hop else "  |-"
                
                # Parse action từ reason (format: "[ACTION] reason_text")
                reason_text = hop.reason
                action = ""
                if reason_text.startswith("["):
                    bracket_end = reason_text.find("]")
                    if bracket_end > 0:
                        action = reason_text[1:bracket_end]
                        reason_text = reason_text[bracket_end+2:]
                
                from_str = f"N{hop.from_node}"
                to_str = f"N{hop.to_node}" if hop.to_node is not None else "?"
                lines.append(f"{prefix} [{i+1}] {from_str} --{action}--> {to_str}  ({reason_text})")
            
            # GET result
            posting_str = "{" + ", ".join(str(d) for d in sorted(lookup.posting_list)) + "}"
            resp_peer = f"N{lookup.responsible_peer}" if lookup.responsible_peer else "?"
            lines.append(f"  \\- GET {resp_peer} -> posting_list: {posting_str}")
            
            # Running intersection
            current_set = set(lookup.posting_list)
            if running_intersection is None:
                running_intersection = current_set
            else:
                prev = running_intersection.copy()
                running_intersection = running_intersection.intersection(current_set)
                prev_str = "{" + ", ".join(str(d) for d in sorted(prev)) + "}"
                curr_str = "{" + ", ".join(str(d) for d in sorted(current_set)) + "}"
                inter_str = "{" + ", ".join(str(d) for d in sorted(running_intersection)) + "}"
                lines.append(f"  INTERSECT  {prev_str} AND {curr_str} = {inter_str}")
            
            if idx < len(result.trace) - 1:
                lines.append("")
        
        lines.append("")
        final_str = "{" + ", ".join(str(d) for d in sorted(result.final_result)) + "}"
        lines.append(f"  Final result: {final_str} ({len(result.final_result)} docs)")
        lines.append(f"  Routing hops: {result.total_hops} | Flags: {result.flags}")
        if result.warnings:
            for w in result.warnings:
                lines.append(f"  [!] {w}")
        lines.append(sep)
        
        return "\n".join(lines)

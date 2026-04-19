from typing import List, Set, Any, Dict
from src.chord.ring import ChordRing
from src.models import KeywordLookup, HopEvent, QueryResult, ExecutionStatus, ResultStatus
from src.chord.utils import deterministic_hash

class QueryEngine:
    def __init__(self, ring: ChordRing):
        self.ring = ring
        
    def query_and(self, initiator_id: int, raw_query: str) -> QueryResult:
        """
        Thực hiện tìm kiếm giao hoán theo chuẩn Idea 4: Incremental Fetch + Early Stop.
        Chỉ tính toán và giao hoán trên Client (initiator), không modify core routing.
        """
        # 1. Tiền xử lý truy vấn
        # Phân tách ngầm định toán tử khoảng trắng là AND.
        keywords = [k for k in raw_query.lower().split() if k != "and"]
        
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
        except ValueError:
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
            
        start_log_idx = len(self.ring.transport.message_log)
        
        final_doc_ids: Set[int] = set()
        trace_list: List[KeywordLookup] = []
        warnings: List[str] = []
        flags: Dict[str, bool] = {"early_stop": False, "partial_data": False}
        is_first_keyword = True
        
        for k in keywords:
            kw_start_idx = len(self.ring.transport.message_log)
            
            # --- FETCH MẠNG BẰNG ĐÓNG GÓI RESPONSE ---
            api_response = initiator_node.get(k)
            
            # Xử lý phân biệt rõng do Không Tồn Tại hay rỗng do Mạng Chết
            if not api_response.success:
                warnings.append(f"Network / Node unreachable for keyword: '{k}'. Failed Fetch.")
                flags["partial_data"] = True
                current_doc_ids = set()
            else:
                current_doc_ids = set(api_response.data.get("doc_ids", []))
            
            # --- TRACING ---
            new_logs = self.ring.transport.message_log[kw_start_idx:]
            hops = []
            target_peer = None
            
            for log_entry in new_logs:
                msg = log_entry["message"]
                to_node = log_entry["to"]
                
                if msg.type == "FIND_SUCCESSOR":
                    # Tracer suy đoán nguyên nhân
                    reason = f"Routing step for '{k}'"
                    hops.append(HopEvent(
                        hop_number=len(hops) + 1,
                        from_node=msg.sender_id,
                        to_node=to_node,
                        reason=reason
                    ))
                elif msg.type == "GET":
                    target_peer = to_node
                    hops.append(HopEvent(
                        hop_number=len(hops) + 1,
                        from_node=msg.sender_id,
                        to_node=to_node,
                        reason="Final GET payload"
                    ))
                    
            if target_peer is None and api_response.success is False:
                 pass # Logic tracer vẫn giữ nguyên.
            
            kw_lookup = KeywordLookup(
                keyword=k,
                hash_value=deterministic_hash(k, initiator_node.m),
                responsible_peer=target_peer,
                posting_list=list(current_doc_ids),
                hops=len(hops),
                routing_path=hops
            )
            trace_list.append(kw_lookup)
            
            # --- INCREMENTAL INTERSECT & EARLY STOP ---
            # Nếu network gọi lỗi (partial_data=True), bỏ qua intersect thay vì gán tập rỗng để cứu vớt các từ khóa còn lại 
            # (Hoặc gán rỗng tuỳ chiến lược, ta sẽ gán rỗng như một tính năng rớt mạng chặt chẽ)
            if is_first_keyword:
                final_doc_ids = current_doc_ids
                is_first_keyword = False
            else:
                final_doc_ids = final_doc_ids.intersection(current_doc_ids)
                
            # Idea 4: Ngắt mạch sớm nếu giao hoán thành tập rỗng
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
            
        total_messages = len(self.ring.transport.message_log) - start_log_idx
        
        return QueryResult(
            query=raw_query,
            execution_status=exec_status,
            result_status=res_status,
            total_hops=total_messages,
            initiator_peer=initiator_id,
            final_result=list(final_doc_ids),
            flags=flags,
            warnings=warnings,
            trace=trace_list
        )

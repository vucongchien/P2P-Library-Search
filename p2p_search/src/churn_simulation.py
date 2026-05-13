"""
Churn Simulation — Mô phỏng node rời mạng và đo tác động.

Flow:
  1. Snapshot metrics TRƯỚC churn
  2. Chạy query benchmark TRƯỚC churn  
  3. Remove node → stabilize
  4. Snapshot metrics SAU churn
  5. Chạy CÙNG query benchmark SAU churn
  6. So sánh kết quả → ChurnReport
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

from src.chord.ring import ChordRing
from src.query_engine import QueryEngine
from src.metrics import MetricsCollector, BatchMetrics, ChurnDelta

logger = logging.getLogger(__name__)


@dataclass
class ChurnReport:
    """Báo cáo đầy đủ cho 1 sự kiện churn."""
    removed_node_id: int
    stabilize_rounds: int
    
    # Metrics trước/sau
    metrics_delta: ChurnDelta
    
    # Query accuracy
    queries_tested: List[str]
    before_results: Dict[str, List[int]]   # query → doc_ids
    after_results: Dict[str, List[int]]
    all_queries_match: bool
    mismatched_queries: List[str]
    
    # DHT data
    keys_on_removed_node: int
    keys_recovered_from_replica: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "removed_node_id": self.removed_node_id,
            "stabilize_rounds": self.stabilize_rounds,
            "metrics_delta": self.metrics_delta.to_dict(),
            "queries_tested": self.queries_tested,
            "before_results": {q: sorted(ids) for q, ids in self.before_results.items()},
            "after_results": {q: sorted(ids) for q, ids in self.after_results.items()},
            "all_queries_match": self.all_queries_match,
            "mismatched_queries": self.mismatched_queries,
            "keys_on_removed_node": self.keys_on_removed_node,
            "keys_recovered_from_replica": self.keys_recovered_from_replica,
        }

    def format_readable(self) -> str:
        """Format readable cho report."""
        sep = "═" * 60
        lines = [
            sep,
            f"  CHURN REPORT: Node {self.removed_node_id} removed",
            sep,
            f"  Stabilize rounds: {self.stabilize_rounds}",
            f"  Keys on removed node: {self.keys_on_removed_node}",
            f"  Keys recovered from replica: {self.keys_recovered_from_replica}",
            "",
            f"  Messages before: {self.metrics_delta.before.total_messages}",
            f"  Messages after:  {self.metrics_delta.after.total_messages}",
            f"  Messages delta:  +{self.metrics_delta.messages_delta}",
            "",
            f"  Queries tested: {len(self.queries_tested)}",
            f"  All match: {'✅ YES' if self.all_queries_match else '❌ NO'}",
        ]
        
        if self.mismatched_queries:
            lines.append(f"  Mismatched: {self.mismatched_queries}")
        
        for q in self.queries_tested:
            before = sorted(self.before_results.get(q, []))
            after = sorted(self.after_results.get(q, []))
            match = "✅" if before == after else "❌"
            lines.append(f"  {match} \"{q}\": before={before} after={after}")
        
        lines.append(sep)
        return "\n".join(lines)


class ChurnSimulator:
    """
    Chạy mô phỏng churn: remove node → stabilize → verify queries.
    """
    
    def __init__(self, ring: ChordRing, metrics: MetricsCollector):
        self.ring = ring
        self.metrics = metrics
    
    def simulate(
        self,
        node_to_remove: int,
        test_queries: List[str],
        initiator_id: Optional[int] = None,
        stabilize_rounds: int = 3,
    ) -> ChurnReport:
        """
        Chạy full churn simulation.
        
        Args:
            node_to_remove: ID node sẽ bị xóa
            test_queries: Danh sách query để test trước/sau
            initiator_id: Node khởi tạo query (mặc định: node đầu tiên không bị xóa)
            stabilize_rounds: Số vòng stabilize sau khi xóa node
            
        Returns:
            ChurnReport chi tiết
        """
        if node_to_remove not in self.ring.nodes:
            raise ValueError(f"Node {node_to_remove} không tồn tại trong ring.")
        
        # Chọn initiator (không phải node bị xóa)
        if initiator_id is None:
            for nid in sorted(self.ring.nodes.keys()):
                if nid != node_to_remove:
                    initiator_id = nid
                    break
        
        if initiator_id is None:
            raise ValueError("Không có node nào khác để làm initiator.")
        
        qe = QueryEngine(self.ring)
        
        # === PHASE 1: BEFORE CHURN ===
        logger.info(f"[Churn] Phase 1: Benchmark BEFORE removing N{node_to_remove}")
        
        # Đếm keys trên node sắp bị xóa
        target_node = self.ring.nodes[node_to_remove]
        keys_on_removed = len(target_node.dht_store)
        removed_keywords = set(target_node.dht_store.keys())
        
        # Snapshot metrics
        before_snapshot = self.metrics.snapshot()
        
        # Chạy queries trước churn
        before_results: Dict[str, List[int]] = {}
        for q in test_queries:
            result = qe.query_and(initiator_id, q)
            before_results[q] = sorted(result.final_result)
            logger.info(f"  Before query \"{q}\": {before_results[q]}")
        
        # === PHASE 2: REMOVE NODE ===
        logger.info(f"[Churn] Phase 2: Removing N{node_to_remove}")
        self.ring.remove_node(node_to_remove)
        
        # === PHASE 3: STABILIZE ===
        logger.info(f"[Churn] Phase 3: Stabilizing ({stabilize_rounds} rounds)")
        self.ring.stabilize_all(rounds=stabilize_rounds)
        
        # === PHASE 4: AFTER CHURN ===
        logger.info(f"[Churn] Phase 4: Benchmark AFTER churn")
        
        # Snapshot metrics sau
        after_snapshot = self.metrics.snapshot()
        
        # Chạy queries sau churn
        after_results: Dict[str, List[int]] = {}
        for q in test_queries:
            result = qe.query_and(initiator_id, q)
            after_results[q] = sorted(result.final_result)
            logger.info(f"  After query \"{q}\": {after_results[q]}")
        
        # === PHASE 5: SO SÁNH ===
        logger.info(f"[Churn] Phase 5: Comparing results")
        
        mismatched = []
        for q in test_queries:
            if before_results[q] != after_results[q]:
                mismatched.append(q)
                logger.warning(f"  MISMATCH \"{q}\": {before_results[q]} -> {after_results[q]}")
        
        # Kiểm tra keys recovered từ replica
        keys_recovered = 0
        for keyword in removed_keywords:
            # Check xem keyword có tồn tại ở node nào không (qua replica_store hoặc dht_store)
            for nid, node in self.ring.nodes.items():
                if keyword in node.dht_store or keyword in getattr(node, 'replica_store', {}):
                    keys_recovered += 1
                    break
        
        delta = self.metrics.compare(
            before_snapshot, after_snapshot,
            # Không truyền query results vào compare vì ta đã so sánh thủ công ở trên
        )
        
        report = ChurnReport(
            removed_node_id=node_to_remove,
            stabilize_rounds=stabilize_rounds,
            metrics_delta=delta,
            queries_tested=test_queries,
            before_results=before_results,
            after_results=after_results,
            all_queries_match=len(mismatched) == 0,
            mismatched_queries=mismatched,
            keys_on_removed_node=keys_on_removed,
            keys_recovered_from_replica=keys_recovered,
        )
        
        logger.info(f"[Churn] Done. Match={report.all_queries_match}, "
                     f"Keys lost={keys_on_removed}, Recovered={keys_recovered}")
        
        return report

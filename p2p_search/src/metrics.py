"""
Module Metrics: Đo lường hiệu năng hệ thống P2P.

Nguồn dữ liệu:
  - transport.message_log: List[{"from": int, "to": int, "type": str, "message": Message, "timestamp": float}]
  - ChordRing.nodes: Dict[int, ChordNode]  (đọc dht_store, replica_store)
  - QueryResult.trace: routing trace THẬT từ routing layer (source of truth)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)


# ============================================================
# Dataclasses đầu ra
# ============================================================

@dataclass
class QueryStats:
    """Thống kê chi tiết cho 1 query."""
    query: str
    total_hops: int
    total_messages: int
    avg_hops_per_keyword: float
    keywords_count: int
    result_count: int
    early_stopped: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_hops": self.total_hops,
            "total_messages": self.total_messages,
            "avg_hops_per_keyword": round(self.avg_hops_per_keyword, 2),
            "keywords_count": self.keywords_count,
            "result_count": self.result_count,
            "early_stopped": self.early_stopped,
        }


@dataclass
class NodeTraffic:
    """Lưu lượng mạng của 1 node."""
    node_id: int
    sent: int = 0
    received: int = 0
    by_type_sent: Dict[str, int] = field(default_factory=dict)
    by_type_received: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "sent": self.sent,
            "received": self.received,
            "by_type_sent": dict(self.by_type_sent),
            "by_type_received": dict(self.by_type_received),
        }


@dataclass
class BatchMetrics:
    """Báo cáo tổng hợp toàn hệ thống."""
    total_messages: int = 0
    messages_by_type: Dict[str, int] = field(default_factory=dict)
    node_traffic: List[NodeTraffic] = field(default_factory=list)

    # Query performance
    query_stats: List[QueryStats] = field(default_factory=list)
    avg_hops_per_query: float = 0.0
    avg_messages_per_query: float = 0.0

    # DHT health
    total_keys_in_dht: int = 0
    keys_distribution: Dict[int, int] = field(default_factory=dict)
    replication_coverage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "messages_by_type": dict(self.messages_by_type),
            "node_traffic": [n.to_dict() for n in self.node_traffic],
            "query_stats": [q.to_dict() for q in self.query_stats],
            "avg_hops_per_query": round(self.avg_hops_per_query, 2),
            "avg_messages_per_query": round(self.avg_messages_per_query, 2),
            "total_keys_in_dht": self.total_keys_in_dht,
            "keys_distribution": dict(self.keys_distribution),
            "replication_coverage": round(self.replication_coverage, 2),
        }


@dataclass
class ChurnDelta:
    """So sánh metrics trước/sau churn."""
    before: BatchMetrics
    after: BatchMetrics
    messages_delta: int = 0
    avg_hops_delta: float = 0.0
    keys_lost: int = 0
    keys_recovered_from_replica: int = 0
    query_results_match: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "messages_delta": self.messages_delta,
            "avg_hops_delta": round(self.avg_hops_delta, 2),
            "keys_lost": self.keys_lost,
            "keys_recovered_from_replica": self.keys_recovered_from_replica,
            "query_results_match": self.query_results_match,
        }


# ============================================================
# MetricsCollector
# ============================================================

class MetricsCollector:
    """
    Thu thập và phân tích metrics từ transport.message_log + ChordRing state.

    Nguyên tắc:
    - CHỈ ĐỌC, không ghi.
    - Không import chord logic, chỉ đọc attribute.
    - Có thể dùng lại cho cả LocalTransport và NetworkTransport.
    """

    def __init__(self, transport, ring=None):
        """
        Args:
            transport: Transport instance (có .message_log)
            ring: ChordRing instance (optional, để đọc DHT state)
        """
        self.transport = transport
        self.ring = ring
        self._query_results = []

    # ----------------------------------------------------------
    # Message log analysis
    # ----------------------------------------------------------

    def total_messages(self, start_idx: int = 0, end_idx: int | None = None) -> int:
        """Tổng số message trong khoảng log chỉ định."""
        log_slice = self._get_log_slice(start_idx, end_idx)
        return len(log_slice)

    def messages_by_type(self, start_idx: int = 0, end_idx: int | None = None) -> Dict[str, int]:
        """Đếm message theo loại (FIND_SUCCESSOR, GET, PUT, ...)."""
        log_slice = self._get_log_slice(start_idx, end_idx)
        counter = Counter()
        for entry in log_slice:
            msg_type = entry.get("type", entry["message"].type)
            counter[msg_type] += 1
        return dict(counter)

    def bandwidth_by_node(self, start_idx: int = 0, end_idx: int | None = None) -> Dict[int, NodeTraffic]:
        """Phân tích lưu lượng gửi/nhận của từng node."""
        log_slice = self._get_log_slice(start_idx, end_idx)
        traffic: Dict[int, NodeTraffic] = {}

        for entry in log_slice:
            sender_id = entry.get("from", entry["message"].sender_id)
            receiver_id = entry["to"]
            msg_type = entry.get("type", entry["message"].type)

            # Sender
            if sender_id not in traffic:
                traffic[sender_id] = NodeTraffic(node_id=sender_id)
            traffic[sender_id].sent += 1
            traffic[sender_id].by_type_sent[msg_type] = \
                traffic[sender_id].by_type_sent.get(msg_type, 0) + 1

            # Receiver
            if receiver_id not in traffic:
                traffic[receiver_id] = NodeTraffic(node_id=receiver_id)
            traffic[receiver_id].received += 1
            traffic[receiver_id].by_type_received[msg_type] = \
                traffic[receiver_id].by_type_received.get(msg_type, 0) + 1

        return traffic

    # ----------------------------------------------------------
    # Query analysis
    # ----------------------------------------------------------

    def add_query_result(self, query_result) -> None:
        """Thêm QueryResult để phân tích sau."""
        self._query_results.append(query_result)

    def analyze_query(self, query_result) -> QueryStats:
        """Phân tích chi tiết 1 QueryResult. Dùng trace thật từ routing."""
        lookups = query_result.trace
        keywords_count = len(lookups)
        
        # total_hops: tổng routing hops thật từ trace (source of truth)
        total_hops = sum(lk.hops for lk in lookups)
        avg_hops = total_hops / keywords_count if keywords_count > 0 else 0.0

        return QueryStats(
            query=query_result.query,
            total_hops=total_hops,
            total_messages=query_result.total_hops,
            avg_hops_per_keyword=avg_hops,
            keywords_count=keywords_count,
            result_count=len(query_result.final_result),
            early_stopped=query_result.flags.get("early_stop", False),
        )

    # ----------------------------------------------------------
    # DHT health (cần ring)
    # ----------------------------------------------------------

    def _collect_dht_health(self) -> Dict[str, Any]:
        """Thu thập chỉ số sức khỏe DHT từ ring state."""
        if self.ring is None:
            return {
                "total_keys_in_dht": 0,
                "keys_distribution": {},
                "replication_coverage": 0.0,
            }

        all_dht_keys = set()
        all_replica_keys = set()
        keys_dist: Dict[int, int] = {}

        for node_id, node in self.ring.nodes.items():
            num_keys = len(node.dht_store)
            keys_dist[node_id] = num_keys
            all_dht_keys.update(node.dht_store.keys())

            if hasattr(node, "replica_store"):
                all_replica_keys.update(node.replica_store.keys())

        total_keys = len(all_dht_keys)
        # Replication coverage: % keys có ít nhất 1 replica
        replicated = len(all_dht_keys & all_replica_keys)
        coverage = replicated / total_keys if total_keys > 0 else 0.0

        return {
            "total_keys_in_dht": total_keys,
            "keys_distribution": keys_dist,
            "replication_coverage": coverage,
        }

    # ----------------------------------------------------------
    # Report generation
    # ----------------------------------------------------------

    def generate_report(self) -> BatchMetrics:
        """Tổng hợp toàn bộ metrics thành 1 report."""
        total = self.total_messages()
        by_type = self.messages_by_type()
        traffic_map = self.bandwidth_by_node()
        traffic_list = sorted(traffic_map.values(), key=lambda t: t.node_id)

        # Query stats
        q_stats = [self.analyze_query(qr) for qr in self._query_results]
        avg_hops = (
            sum(qs.total_hops for qs in q_stats) / len(q_stats)
            if q_stats else 0.0
        )
        avg_msgs = (
            sum(qs.total_messages for qs in q_stats) / len(q_stats)
            if q_stats else 0.0
        )

        # DHT health
        dht = self._collect_dht_health()

        return BatchMetrics(
            total_messages=total,
            messages_by_type=by_type,
            node_traffic=traffic_list,
            query_stats=q_stats,
            avg_hops_per_query=avg_hops,
            avg_messages_per_query=avg_msgs,
            total_keys_in_dht=dht["total_keys_in_dht"],
            keys_distribution=dht["keys_distribution"],
            replication_coverage=dht["replication_coverage"],
        )

    # ----------------------------------------------------------
    # Snapshot & Compare (Churn)
    # ----------------------------------------------------------

    def snapshot(self) -> BatchMetrics:
        """Chụp trạng thái hiện tại — alias cho generate_report."""
        return self.generate_report()

    def compare(self, before: BatchMetrics, after: BatchMetrics,
                before_query_results=None, after_query_results=None) -> ChurnDelta:
        """So sánh 2 snapshot trước/sau sự kiện churn."""
        messages_delta = after.total_messages - before.total_messages
        avg_hops_delta = after.avg_hops_per_query - before.avg_hops_per_query

        # Keys lost = keys trước - keys sau
        before_keys = set()
        after_keys = set()
        
        if self.ring is not None:
            # Nếu có ring, tính từ distribution
            before_keys = set(k for k in before.keys_distribution.keys())
            after_keys = set(k for k in after.keys_distribution.keys())
        
        keys_lost = before.total_keys_in_dht - after.total_keys_in_dht
        keys_lost = max(0, keys_lost)

        # So sánh query results nếu có
        query_match = True
        if before_query_results and after_query_results:
            for bq, aq in zip(before_query_results, after_query_results):
                if set(bq.final_result) != set(aq.final_result):
                    query_match = False
                    break

        return ChurnDelta(
            before=before,
            after=after,
            messages_delta=messages_delta,
            avg_hops_delta=avg_hops_delta,
            keys_lost=keys_lost,
            query_results_match=query_match,
        )

    # ----------------------------------------------------------
    # Utilities
    # ----------------------------------------------------------

    def _get_log_slice(self, start_idx: int = 0, end_idx: int | None = None) -> list:
        """Lấy slice của message_log."""
        if end_idx is None:
            return self.transport.message_log[start_idx:]
        return self.transport.message_log[start_idx:end_idx]

    def reset_query_results(self) -> None:
        """Xóa danh sách query results đã lưu."""
        self._query_results.clear()

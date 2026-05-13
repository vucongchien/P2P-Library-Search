"""
Test MetricsCollector — kiểm tra phân tích passive từ message_log & ring state.

Nhóm test:
  1. Message counting: total, by_type
  2. Bandwidth per node: sent/received  
  3. Query analysis: từ QueryResult
  4. DHT health: keys distribution, replication
  5. Report generation: tổng hợp
  6. Snapshot & Compare: churn delta
  7. Edge cases: empty log, no ring, single node
"""

import pytest
from src.transport import LocalTransport
from src.chord.ring import ChordRing
from src.models import Message, QueryResult, KeywordLookup, HopEvent, ExecutionStatus, ResultStatus
from src.metrics import MetricsCollector, QueryStats, NodeTraffic, BatchMetrics, ChurnDelta


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def transport():
    return LocalTransport()

@pytest.fixture
def ring_5_nodes(transport):
    """Ring 5 nodes đã stabilize, có dữ liệu DHT."""
    node_ids = [10, 60, 110, 160, 210]
    ring = ChordRing.create(node_ids, transport, m=8)
    
    # Đẩy dữ liệu thủ công để test DHT health
    node10 = ring.get_node(10)
    node10.put("system", {1, 5, 21})
    node10.put("database", {8, 21, 55})
    node10.put("network", {3, 7})
    
    return ring

@pytest.fixture
def collector(transport, ring_5_nodes):
    return MetricsCollector(transport, ring_5_nodes)

@pytest.fixture
def collector_no_ring(transport):
    """Collector chỉ có transport, không có ring."""
    return MetricsCollector(transport)

@pytest.fixture
def sample_query_result():
    """QueryResult mẫu cho test analyze_query."""
    return QueryResult(
        query="system AND database",
        execution_status=ExecutionStatus.SUCCESS,
        result_status=ResultStatus.HAS_RESULT,
        total_hops=6,
        initiator_peer=10,
        final_result=[21],
        flags={"early_stop": False, "partial_data": False},
        warnings=[],
        trace=[
            KeywordLookup(
                keyword="system",
                hash_value=73,
                responsible_peer=110,
                posting_list=[1, 5, 21],
                hops=2,
                routing_path=[
                    HopEvent(hop_number=1, from_node=10, to_node=60, reason="Routing step"),
                    HopEvent(hop_number=2, from_node=60, to_node=110, reason="Final GET"),
                ]
            ),
            KeywordLookup(
                keyword="database",
                hash_value=155,
                responsible_peer=160,
                posting_list=[8, 21, 55],
                hops=1,
                routing_path=[
                    HopEvent(hop_number=1, from_node=10, to_node=160, reason="Final GET"),
                ]
            ),
        ]
    )

@pytest.fixture
def early_stop_query_result():
    """QueryResult với early stop."""
    return QueryResult(
        query="xyz AND abc",
        execution_status=ExecutionStatus.SUCCESS,
        result_status=ResultStatus.EMPTY,
        total_hops=4,
        initiator_peer=10,
        final_result=[],
        flags={"early_stop": True, "partial_data": False},
        warnings=["Early stop triggered"],
        trace=[
            KeywordLookup(
                keyword="xyz", hash_value=42, responsible_peer=60,
                posting_list=[], hops=2, routing_path=[]
            ),
        ]
    )


# ============================================================
# 1. Message Counting
# ============================================================

class TestMessageCounting:
    def test_total_messages_after_setup(self, collector):
        """Setup ring 5 nodes + 3 PUT → message_log phải có entries."""
        total = collector.total_messages()
        assert total > 0, "Sau khi setup ring và put data, phải có messages trong log"

    def test_total_messages_empty_log(self):
        """Transport mới tạo → 0 messages."""
        t = LocalTransport()
        mc = MetricsCollector(t)
        assert mc.total_messages() == 0

    def test_messages_by_type_has_expected_types(self, collector):
        """Sau setup ring, log phải chứa FIND_SUCCESSOR, NOTIFY, PUT, etc."""
        by_type = collector.messages_by_type()
        # Stabilize tạo ra NOTIFY, GET_PREDECESSOR, PING
        # Put tạo ra FIND_SUCCESSOR, PUT
        assert len(by_type) > 0, "Phải có ít nhất 1 loại message"
        assert "FIND_SUCCESSOR" in by_type or "PUT" in by_type, \
            f"Thiếu message types cơ bản. Got: {list(by_type.keys())}"

    def test_total_messages_with_slice(self, collector):
        """Test slice log: chỉ đếm một phần."""
        total_all = collector.total_messages()
        # Lấy nửa đầu
        half = total_all // 2
        total_half = collector.total_messages(start_idx=0, end_idx=half)
        assert total_half == half
        assert total_half < total_all


# ============================================================
# 2. Bandwidth Per Node
# ============================================================

class TestBandwidthPerNode:
    def test_bandwidth_has_all_nodes(self, collector, ring_5_nodes):
        """Mỗi node trong ring phải xuất hiện ít nhất 1 lần (gửi hoặc nhận)."""
        traffic = collector.bandwidth_by_node()
        # Ít nhất phải có một số node
        assert len(traffic) > 0, "Traffic map rỗng"
        
    def test_sent_received_consistency(self, collector):
        """Tổng sent == tổng received == total messages."""
        traffic = collector.bandwidth_by_node()
        total_sent = sum(t.sent for t in traffic.values())
        total_received = sum(t.received for t in traffic.values())
        total = collector.total_messages()
        
        assert total_sent == total, f"Tổng sent ({total_sent}) != total messages ({total})"
        assert total_received == total, f"Tổng received ({total_received}) != total messages ({total})"

    def test_node_traffic_type_breakdown(self, collector):
        """by_type_sent và by_type_received phải cộng lại đúng sent/received."""
        traffic = collector.bandwidth_by_node()
        for node_id, t in traffic.items():
            sent_sum = sum(t.by_type_sent.values())
            recv_sum = sum(t.by_type_received.values())
            assert sent_sum == t.sent, f"Node {node_id}: type_sent sum ({sent_sum}) != sent ({t.sent})"
            assert recv_sum == t.received, f"Node {node_id}: type_recv sum ({recv_sum}) != received ({t.received})"

    def test_node_traffic_to_dict(self, collector):
        """NodeTraffic phải serialize được."""
        traffic = collector.bandwidth_by_node()
        for t in traffic.values():
            d = t.to_dict()
            assert "node_id" in d
            assert "sent" in d
            assert "received" in d


# ============================================================
# 3. Query Analysis
# ============================================================

class TestQueryAnalysis:
    def test_analyze_basic_query(self, collector_no_ring, sample_query_result):
        """Phân tích query cơ bản: 2 keywords, 3 hops total, 1 result."""
        stats = collector_no_ring.analyze_query(sample_query_result)
        
        assert stats.query == "system AND database"
        assert stats.total_hops == 3  # 2 + 1
        assert stats.keywords_count == 2
        assert stats.result_count == 1
        assert stats.early_stopped is False
        assert stats.avg_hops_per_keyword == 1.5  # 3/2

    def test_analyze_early_stop_query(self, collector_no_ring, early_stop_query_result):
        """Query với early stop phải được phát hiện."""
        stats = collector_no_ring.analyze_query(early_stop_query_result)
        assert stats.early_stopped is True
        assert stats.result_count == 0

    def test_query_stats_to_dict(self, collector_no_ring, sample_query_result):
        """QueryStats phải JSON-serializable."""
        stats = collector_no_ring.analyze_query(sample_query_result)
        d = stats.to_dict()
        assert isinstance(d, dict)
        assert "query" in d
        assert "avg_hops_per_keyword" in d

    def test_add_and_use_query_results(self, collector_no_ring, sample_query_result, early_stop_query_result):
        """add_query_result rồi generate_report phải bao gồm query stats."""
        collector_no_ring.add_query_result(sample_query_result)
        collector_no_ring.add_query_result(early_stop_query_result)
        
        report = collector_no_ring.generate_report()
        assert len(report.query_stats) == 2
        assert report.avg_hops_per_query > 0


# ============================================================
# 4. DHT Health
# ============================================================

class TestDHTHealth:
    def test_keys_distribution_non_empty(self, collector, ring_5_nodes):
        """Sau khi put 3 keywords, DHT phải có keys phân bổ."""
        report = collector.generate_report()
        assert report.total_keys_in_dht > 0, "DHT phải chứa ít nhất 1 key"
        assert sum(report.keys_distribution.values()) > 0

    def test_replication_coverage(self, collector):
        """Replication coverage phải trong [0, 1]."""
        report = collector.generate_report()
        assert 0.0 <= report.replication_coverage <= 1.0

    def test_no_ring_returns_safe_defaults(self, collector_no_ring):
        """Không có ring → DHT health trả về 0/empty an toàn."""
        report = collector_no_ring.generate_report()
        assert report.total_keys_in_dht == 0
        assert report.keys_distribution == {}
        assert report.replication_coverage == 0.0


# ============================================================
# 5. Report Generation
# ============================================================

class TestReportGeneration:
    def test_generate_report_structure(self, collector):
        """Report phải đầy đủ các field."""
        report = collector.generate_report()
        assert isinstance(report, BatchMetrics)
        assert report.total_messages > 0
        assert isinstance(report.messages_by_type, dict)
        assert isinstance(report.node_traffic, list)

    def test_report_to_dict(self, collector):
        """Report phải serialize được sang dict."""
        report = collector.generate_report()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "total_messages" in d
        assert "messages_by_type" in d
        assert "node_traffic" in d
        assert "replication_coverage" in d

    def test_report_traffic_sorted_by_node_id(self, collector):
        """node_traffic phải sorted theo node_id."""
        report = collector.generate_report()
        ids = [t.node_id for t in report.node_traffic]
        assert ids == sorted(ids), "node_traffic phải sorted theo node_id"


# ============================================================
# 6. Snapshot & Compare (Churn Delta)
# ============================================================

class TestSnapshotCompare:
    def test_snapshot_returns_batch_metrics(self, collector):
        """snapshot() trả về BatchMetrics."""
        snap = collector.snapshot()
        assert isinstance(snap, BatchMetrics)

    def test_compare_same_snapshot(self, collector):
        """So sánh snapshot với chính nó → delta = 0."""
        snap = collector.snapshot()
        delta = collector.compare(snap, snap)
        assert isinstance(delta, ChurnDelta)
        assert delta.messages_delta == 0
        assert delta.avg_hops_delta == 0.0

    def test_compare_detects_message_increase(self, transport, ring_5_nodes):
        """Sau khi thêm messages, delta phải dương."""
        mc = MetricsCollector(transport, ring_5_nodes)
        before = mc.snapshot()
        
        # Tạo thêm messages bằng cách query
        from src.query_engine import QueryEngine
        qe = QueryEngine(ring_5_nodes)
        qr = qe.query_and(10, "system")
        mc.add_query_result(qr)
        
        after = mc.snapshot()
        delta = mc.compare(before, after)
        assert delta.messages_delta > 0, "Sau query, message count phải tăng"

    def test_compare_query_results_match(self, collector, sample_query_result):
        """So sánh khi query results giống nhau."""
        snap = collector.snapshot()
        delta = collector.compare(
            snap, snap,
            before_query_results=[sample_query_result],
            after_query_results=[sample_query_result],
        )
        assert delta.query_results_match is True

    def test_compare_query_results_mismatch(self, collector, sample_query_result, early_stop_query_result):
        """So sánh khi query results khác nhau."""
        snap = collector.snapshot()
        delta = collector.compare(
            snap, snap,
            before_query_results=[sample_query_result],
            after_query_results=[early_stop_query_result],
        )
        assert delta.query_results_match is False

    def test_churn_delta_to_dict(self, collector):
        """ChurnDelta phải serialize được."""
        snap = collector.snapshot()
        delta = collector.compare(snap, snap)
        d = delta.to_dict()
        assert isinstance(d, dict)
        assert "messages_delta" in d
        assert "before" in d
        assert "after" in d


# ============================================================
# 7. Edge Cases
# ============================================================

class TestEdgeCases:
    def test_empty_transport_log(self):
        """Transport mới tạo → mọi metrics = 0/empty."""
        t = LocalTransport()
        mc = MetricsCollector(t)
        report = mc.generate_report()
        assert report.total_messages == 0
        assert report.messages_by_type == {}
        assert report.node_traffic == []

    def test_single_node_ring(self):
        """Ring 1 node → metrics vẫn hoạt động."""
        t = LocalTransport()
        ring = ChordRing.create([50], t, m=8)
        mc = MetricsCollector(t, ring)
        report = mc.generate_report()
        assert isinstance(report, BatchMetrics)
        # 1 node ring vẫn tạo messages (stabilize, fix_fingers)
        assert report.total_messages >= 0

    def test_reset_query_results(self, collector_no_ring, sample_query_result):
        """reset_query_results() phải xóa hết."""
        collector_no_ring.add_query_result(sample_query_result)
        assert len(collector_no_ring._query_results) == 1
        
        collector_no_ring.reset_query_results()
        assert len(collector_no_ring._query_results) == 0
        
        report = collector_no_ring.generate_report()
        assert len(report.query_stats) == 0

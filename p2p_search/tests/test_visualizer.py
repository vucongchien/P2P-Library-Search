"""
Test NetworkVisualizer — kiểm tra tạo biểu đồ PNG topology & query path.

Nhóm test:
  1. Khởi tạo: visualizer với ring hợp lệ + ring rỗng
  2. Ring topology: tạo file PNG, kích thước > 0
  3. Query path: overlay đường đi lên topology
  4. DHT distribution: bar chart keys
  5. Churn comparison: highlight node đã xóa
  6. Edge cases: 1 node, no data, invalid path
"""

import os
import pytest
from src.transport import LocalTransport
from src.chord.ring import ChordRing
from src.models import QueryResult, KeywordLookup, HopEvent, ExecutionStatus, ResultStatus
from src.visualizer import NetworkVisualizer


# ============================================================
# Fixtures
# ============================================================

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "graphs", "test_output")

@pytest.fixture(autouse=True)
def ensure_output_dir():
    """Tạo thư mục output trước mỗi test."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

@pytest.fixture
def transport():
    return LocalTransport()

@pytest.fixture
def ring_5_nodes(transport):
    """Ring 5 nodes đã stabilize, có dữ liệu DHT."""
    node_ids = [10, 60, 110, 160, 210]
    ring = ChordRing.create(node_ids, transport, m=8)
    node10 = ring.get_node(10)
    node10.put("system", {1, 5, 21})
    node10.put("database", {8, 21, 55})
    node10.put("network", {3, 7})
    return ring

@pytest.fixture
def ring_1_node(transport):
    """Ring 1 node duy nhất."""
    return ChordRing.create([50], transport, m=8)

@pytest.fixture
def visualizer(ring_5_nodes):
    return NetworkVisualizer(ring_5_nodes)

@pytest.fixture
def sample_query_result():
    """QueryResult mẫu cho test draw_query_path."""
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


# ============================================================
# 1. Khởi tạo
# ============================================================

class TestInit:
    def test_init_with_valid_ring(self, ring_5_nodes):
        """Tạo visualizer với ring hợp lệ thành công."""
        viz = NetworkVisualizer(ring_5_nodes)
        assert viz.ring is ring_5_nodes
        assert viz.m == 8

    def test_init_with_single_node_ring(self, ring_1_node):
        """Tạo visualizer với ring 1 node thành công."""
        viz = NetworkVisualizer(ring_1_node)
        assert viz.ring is ring_1_node


# ============================================================
# 2. Ring Topology
# ============================================================

class TestRingTopology:
    def test_draw_creates_png_file(self, visualizer):
        """draw_ring_topology phải tạo file PNG."""
        path = os.path.join(OUTPUT_DIR, "test_topology.png")
        result = visualizer.draw_ring_topology(path)
        
        assert os.path.exists(path), f"File {path} không tồn tại sau khi vẽ"
        assert os.path.getsize(path) > 0, "File PNG rỗng"
        assert result == path

    def test_draw_without_fingers(self, visualizer):
        """Vẽ topology không có finger shortcuts."""
        path = os.path.join(OUTPUT_DIR, "test_topology_no_fingers.png")
        visualizer.draw_ring_topology(path, show_fingers=False)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_draw_custom_title(self, visualizer):
        """Vẽ topology với title tùy chỉnh."""
        path = os.path.join(OUTPUT_DIR, "test_topology_custom.png")
        visualizer.draw_ring_topology(path, title="Custom Test Title")
        assert os.path.exists(path)

    def test_draw_1_node_ring(self, ring_1_node):
        """Vẽ ring 1 node không crash."""
        viz = NetworkVisualizer(ring_1_node)
        path = os.path.join(OUTPUT_DIR, "test_topology_1node.png")
        viz.draw_ring_topology(path)
        assert os.path.exists(path)


# ============================================================
# 3. Query Path
# ============================================================

class TestQueryPath:
    def test_draw_query_path_creates_png(self, visualizer, sample_query_result):
        """draw_query_path phải tạo file PNG với overlay routing."""
        path = os.path.join(OUTPUT_DIR, "test_query_path.png")
        result = visualizer.draw_query_path(sample_query_result, path)
        
        assert os.path.exists(path), f"File {path} không tồn tại"
        assert os.path.getsize(path) > 0
        assert result == path

    def test_draw_query_path_custom_title(self, visualizer, sample_query_result):
        """Query path với title tùy chỉnh."""
        path = os.path.join(OUTPUT_DIR, "test_query_path_custom.png")
        visualizer.draw_query_path(sample_query_result, path, title="Test Query")
        assert os.path.exists(path)


# ============================================================
# 4. DHT Distribution
# ============================================================

class TestDHTDistribution:
    def test_draw_dht_distribution_creates_png(self, visualizer):
        """draw_dht_distribution phải tạo bar chart PNG."""
        path = os.path.join(OUTPUT_DIR, "test_dht_dist.png")
        result = visualizer.draw_dht_distribution(path)
        
        assert os.path.exists(path), f"File {path} không tồn tại"
        assert os.path.getsize(path) > 0
        assert result == path

    def test_draw_dht_distribution_1_node(self, ring_1_node):
        """Bar chart cho ring 1 node."""
        viz = NetworkVisualizer(ring_1_node)
        path = os.path.join(OUTPUT_DIR, "test_dht_dist_1node.png")
        viz.draw_dht_distribution(path)
        assert os.path.exists(path)


# ============================================================
# 5. Churn Comparison
# ============================================================

class TestChurnComparison:
    def test_draw_churn_creates_png(self, visualizer):
        """draw_churn_comparison phải tạo PNG với node chết."""
        path = os.path.join(OUTPUT_DIR, "test_churn.png")
        result = visualizer.draw_churn_comparison([60], path)
        
        assert os.path.exists(path), f"File {path} không tồn tại"
        assert os.path.getsize(path) > 0
        assert result == path

    def test_draw_churn_multiple_nodes(self, visualizer):
        """Churn với nhiều node bị xóa."""
        path = os.path.join(OUTPUT_DIR, "test_churn_multi.png")
        visualizer.draw_churn_comparison([60, 160], path)
        assert os.path.exists(path)

    def test_draw_churn_after_actual_remove(self, transport):
        """Churn thực tế: remove node rồi vẽ."""
        ring = ChordRing.create([10, 60, 110, 160, 210], transport, m=8)
        ring.remove_node(60)
        ring.stabilize_all(rounds=3)
        
        viz = NetworkVisualizer(ring)
        path = os.path.join(OUTPUT_DIR, "test_churn_real.png")
        viz.draw_churn_comparison([60], path)
        assert os.path.exists(path)


# ============================================================
# 6. Edge Cases
# ============================================================

class TestEdgeCases:
    def test_draw_with_empty_ring(self, transport):
        """Ring rỗng → vẽ không crash."""
        ring = ChordRing(transport, m=8)
        viz = NetworkVisualizer(ring)
        path = os.path.join(OUTPUT_DIR, "test_empty_ring.png")
        viz.draw_ring_topology(path)
        # File có thể tạo nhưng rỗng hoặc nhỏ — không crash là pass

    def test_auto_create_directory(self, visualizer):
        """Thư mục output tự động tạo nếu chưa có."""
        deep_path = os.path.join(OUTPUT_DIR, "subdir", "deep", "test_auto.png")
        visualizer.draw_ring_topology(deep_path)
        assert os.path.exists(deep_path)

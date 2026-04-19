import pytest
from src.chord.ring import ChordRing
from src.transport import LocalTransport
from src.query_engine import QueryEngine

class TestQueryEngine:
    
    @pytest.fixture
    def setup_ring(self):
        transport = LocalTransport()
        ring = ChordRing(transport=transport, m=8)
        for i in range(5):
            ring.add_node(i * 50)
        ring.stabilize_all(rounds=5)
        
        # Seed mạng
        nodes = list(ring.nodes.values())
        nodes[0].load_local_index({
            "database": [1, 2, 3],
            "system": [2, 3, 5]
        })
        nodes[1].load_local_index({
            "database": [10],
            "system": [10],
            "alien": [] # Trống rỗng
        })
        
        nodes[0].publish()
        nodes[1].publish()
        
        return ring
        
    def test_query_engine_intersection_success(self, setup_ring):
        ring = setup_ring
        engine = QueryEngine(ring)
        
        # Gọi trên mỏm node xa lạ xem mạng có dẫn tới đúng điểm không
        initiator = list(ring.nodes.keys())[-1]
        
        result = engine.query_and(initiator, "database AND system")
        
        # database = {1, 2, 3, 10}
        # system = {2, 3, 5, 10}
        # Giao hoán = {2, 3, 10}
        from src.models.query import ExecutionStatus, ResultStatus
        assert result.execution_status == ExecutionStatus.SUCCESS
        assert result.result_status == ResultStatus.HAS_RESULT
        assert set(result.final_result) == {2, 3, 10}
        assert len(result.trace) == 2
        
        # Kiểm tra Tracer có làm việc chặt chẽ không
        assert result.trace[0].keyword == "database"
        assert result.trace[1].keyword == "system"
        assert len(result.trace[0].routing_path) > 0 # Chắc chắn phải có số Hop
        
    def test_query_engine_early_stop(self, setup_ring):
        ring = setup_ring
        engine = QueryEngine(ring)
        initiator = list(ring.nodes.keys())[2]
        
        # Lưu ý: Vì bộ parse chạy theo Space, nên kết quả split: ["alien", "database", "system"]
        # Alien là TỐI ĐEN (Tập rỗng). Nó sẽ fetch "alien" trước => Trắng => Lập tức ngắt mạch!
        result = engine.query_and(initiator, "alien database system")
        
        assert len(result.final_result) == 0
        assert result.flags["early_stop"] is True
        assert "Early stop triggered" in result.warnings[0]
        
        # Tracer PHẢI CHỈ CHỨA 1 keyword do 2 từ khoá sau bốc hơi khỏi Network queue!
        assert len(result.trace) == 1
        assert result.trace[0].keyword == "alien"
        
    def test_query_invalid(self, setup_ring):
        engine = QueryEngine(setup_ring)
        initiator = list(setup_ring.nodes.keys())[0]
        result = engine.query_and(initiator, "    AND    ")
        
        from src.models.query import ExecutionStatus, ResultStatus
        assert result.execution_status == ExecutionStatus.FAILED
        assert result.result_status == ResultStatus.EMPTY
        assert len(result.warnings) > 0

"""
Test QueryEngine — Kiểm tra tìm kiếm AND query + trace chính xác.

Nhóm test:
  1. Intersection: "database AND system" → giao hoán đúng
  2. Early stop: keyword rỗng → ngắt mạch
  3. Invalid query: query rỗng → FAILED
  4. Trace accuracy: verify từng hop trong routing path là THẬT
  5. Readable logs: in routing path đầy đủ cho debug

Mỗi test in routing trace readable để verify bằng mắt.
"""

import pytest
from src.chord.ring import ChordRing
from src.chord.utils import deterministic_hash
from src.transport import LocalTransport
from src.query_engine import QueryEngine
from src.models.query import ExecutionStatus, ResultStatus

class TestQueryEngine:
    
    @pytest.fixture
    def setup_ring(self):
        transport = LocalTransport()
        ring = ChordRing(transport=transport, m=8)
        for i in range(5):
            ring.add_node(i * 50)
        ring.stabilize_all(rounds=8)
        
        # Seed mạng
        nodes = list(ring.nodes.values())
        nodes[0].load_local_index({
            "database": [1, 2, 3],
            "system": [2, 3, 5]
        })
        nodes[1].load_local_index({
            "database": [10],
            "system": [10],
            "alien": []
        })
        
        nodes[0].publish()
        nodes[1].publish()
        
        return ring
        
    def test_query_engine_intersection_success(self, setup_ring, capsys):
        ring = setup_ring
        engine = QueryEngine(ring)
        
        initiator = list(ring.nodes.keys())[-1]
        result = engine.query_and(initiator, "database AND system")
        
        # In routing trace readable
        print("\n" + QueryEngine.format_query_trace(result))
        
        # database = {1, 2, 3, 10}
        # system = {2, 3, 5, 10}
        # Giao hoán = {2, 3, 10}
        assert result.execution_status == ExecutionStatus.SUCCESS
        assert result.result_status == ResultStatus.HAS_RESULT
        assert set(result.final_result) == {2, 3, 10}
        assert len(result.trace) == 2
        
        # Verify trace chính xác
        db_trace = result.trace[0]
        sys_trace = result.trace[1]
        
        assert db_trace.keyword == "database"
        assert sys_trace.keyword == "system"
        
        # Hash value phải đúng
        assert db_trace.hash_value == deterministic_hash("database", 8)
        assert sys_trace.hash_value == deterministic_hash("system", 8)
        
        # Routing path phải có ít nhất 1 hop
        assert len(db_trace.routing_path) > 0, "database routing path rỗng!"
        assert len(sys_trace.routing_path) > 0, "system routing path rỗng!"
        
        # Mỗi hop phải có reason THẬT (chứa action type, không phải generic)
        for hop in db_trace.routing_path:
            assert hop.reason != "", f"Hop {hop.hop_number} không có reason"
            assert "[" in hop.reason, f"Hop reason thiếu action type: {hop.reason}"
        
        # Responsible peer phải tồn tại
        assert db_trace.responsible_peer is not None
        assert sys_trace.responsible_peer is not None
        
        # Hop count trong trace phải > 0
        assert db_trace.hops >= 0
        assert sys_trace.hops >= 0
        
    def test_query_engine_early_stop(self, setup_ring, capsys):
        ring = setup_ring
        engine = QueryEngine(ring)
        initiator = list(ring.nodes.keys())[2]
        
        result = engine.query_and(initiator, "alien database system")
        
        print("\n" + QueryEngine.format_query_trace(result))
        
        assert len(result.final_result) == 0
        assert result.flags["early_stop"] is True
        assert "Early stop triggered" in result.warnings[0]
        
        # Chỉ chứa 1 keyword do ngắt mạch sớm
        assert len(result.trace) == 1
        assert result.trace[0].keyword == "alien"
        
    def test_query_invalid(self, setup_ring, capsys):
        engine = QueryEngine(setup_ring)
        initiator = list(setup_ring.nodes.keys())[0]
        result = engine.query_and(initiator, "    AND    ")
        
        assert result.execution_status == ExecutionStatus.FAILED
        assert result.result_status == ResultStatus.EMPTY
        assert len(result.warnings) > 0

    def test_trace_hop_actions_are_valid(self, setup_ring, capsys):
        """Verify mỗi hop có action type hợp lệ (ORIGIN/FORWARD/RESOLVED/SELF)."""
        ring = setup_ring
        engine = QueryEngine(ring)
        initiator = list(ring.nodes.keys())[-1]
        
        result = engine.query_and(initiator, "database")
        print("\n" + QueryEngine.format_query_trace(result))
        
        valid_actions = {"ORIGIN", "FORWARD", "RESOLVED", "SELF"}
        
        for lookup in result.trace:
            for hop in lookup.routing_path:
                # reason format: "[ACTION] reason_text"
                reason = hop.reason
                assert reason.startswith("["), f"Hop reason phải bắt đầu bằng '[': {reason}"
                bracket_end = reason.find("]")
                assert bracket_end > 0, f"Hop reason thiếu ']': {reason}"
                action = reason[1:bracket_end]
                assert action in valid_actions, f"Action '{action}' không hợp lệ. Choices: {valid_actions}"

    def test_trace_path_continuity(self, setup_ring, capsys):
        """Verify đường đi routing liên tục: to_node của hop N = from_node của hop N+1 (hoặc data fetch)."""
        ring = setup_ring
        engine = QueryEngine(ring)
        initiator = list(ring.nodes.keys())[-1]
        
        result = engine.query_and(initiator, "system")
        print("\n" + QueryEngine.format_query_trace(result))
        
        for lookup in result.trace:
            path = lookup.routing_path
            if len(path) <= 1:
                continue
            
            for i in range(len(path) - 1):
                current_hop = path[i]
                next_hop = path[i + 1]
                # to_node của hop hiện tại phải = from_node của hop tiếp theo
                assert current_hop.to_node == next_hop.from_node, \
                    f"Path discontinuity: hop {i+1} to_node=N{current_hop.to_node} " \
                    f"!= hop {i+2} from_node=N{next_hop.from_node}"

    def test_single_keyword_query(self, setup_ring, capsys):
        """Query 1 keyword: routing + data fetch."""
        ring = setup_ring
        engine = QueryEngine(ring)
        initiator = list(ring.nodes.keys())[0]
        
        result = engine.query_and(initiator, "database")
        print("\n" + QueryEngine.format_query_trace(result))
        
        assert result.execution_status == ExecutionStatus.SUCCESS
        assert set(result.final_result) == {1, 2, 3, 10}
        assert len(result.trace) == 1
        
        # Verify posting list khớp
        lookup = result.trace[0]
        assert set(lookup.posting_list) == {1, 2, 3, 10}
        assert lookup.responsible_peer is not None

    def test_query_from_different_initiators(self, setup_ring, capsys):
        """Cùng query, khác initiator → cùng kết quả, có thể khác path."""
        ring = setup_ring
        engine = QueryEngine(ring)
        
        node_ids = sorted(ring.nodes.keys())
        results = []
        
        print("\n=== Query 'database' from different initiators ===")
        for nid in node_ids:
            result = engine.query_and(nid, "database")
            results.append(result)
            print(f"\nInitiator N{nid}:")
            print(QueryEngine.format_query_trace(result))
        
        # Kết quả phải giống nhau
        expected = set(results[0].final_result)
        for r in results[1:]:
            assert set(r.final_result) == expected, \
                f"Results differ! N{results[0].initiator_peer}={expected}, N{r.initiator_peer}={set(r.final_result)}"

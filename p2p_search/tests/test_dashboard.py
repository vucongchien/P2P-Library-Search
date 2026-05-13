"""
Test Dashboard Backend — Unit tests + Integration tests.

Test strategy:
- Unit tests: mock peer responses, test aggregation logic
- Integration test: start real peer servers, test full flow
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard", "backend"))

from fastapi.testclient import TestClient
from dashboard.backend.dashboard_server import create_dashboard_app, _build_local_index, parse_peers


# ============================================================
# TEST: Helper functions
# ============================================================

class TestParsePeers:
    def test_parse_basic(self):
        result = parse_peers("10:8001,60:8002,110:8003")
        assert result == {
            10: "http://127.0.0.1:8001",
            60: "http://127.0.0.1:8002",
            110: "http://127.0.0.1:8003",
        }
    
    def test_parse_single(self):
        result = parse_peers("10:8001")
        assert result == {10: "http://127.0.0.1:8001"}
    
    def test_parse_with_spaces(self):
        result = parse_peers("10:8001, 60:8002")
        assert result == {
            10: "http://127.0.0.1:8001",
            60: "http://127.0.0.1:8002",
        }


class TestBuildLocalIndex:
    def test_basic_tokenize(self):
        docs = [
            {"id": 1, "title": "System Design", "content": "distributed system architecture"},
            {"id": 2, "title": "Database", "content": "query optimization system"},
        ]
        index = _build_local_index(docs)
        
        assert "system" in index
        assert 1 in index["system"]
        assert 2 in index["system"]
        
        assert "distributed" in index
        assert 1 in index["distributed"]
    
    def test_stopwords_removed(self):
        docs = [{"id": 1, "title": "The", "content": "the and or but"}]
        index = _build_local_index(docs)
        assert "the" not in index
        assert "and" not in index
    
    def test_short_words_removed(self):
        docs = [{"id": 1, "title": "AB", "content": "ab cd ef gh"}]
        index = _build_local_index(docs)
        assert "ab" not in index  # len <= 2
    
    def test_empty_docs(self):
        index = _build_local_index([])
        assert index == {}
    
    def test_doc_without_id_skipped(self):
        docs = [{"title": "No ID", "content": "missing identifier"}]
        index = _build_local_index(docs)
        # Should not crash, keywords should map to no valid doc_ids
        for kw, ids in index.items():
            assert len(ids) == 0 or all(isinstance(i, int) for i in ids)


# ============================================================
# TEST: Dashboard endpoints (mocked — peers not running)
# ============================================================

class TestDashboardNoServers:
    """Test dashboard khi peers KHÔNG chạy → graceful degradation."""
    
    @pytest.fixture
    def dashboard(self):
        app = create_dashboard_app(
            peers_config={10: "http://127.0.0.1:19901", 60: "http://127.0.0.1:19902"},
        )
        client = TestClient(app)
        yield client
    
    def test_list_peers_shows_dead(self, dashboard):
        """Peers dead → alive=False."""
        r = dashboard.get("/api/peers")
        assert r.status_code == 200
        data = r.json()
        assert len(data["peers"]) == 2
        for peer in data["peers"]:
            assert peer["alive"] == False
    
    def test_ring_state_returns_warnings(self, dashboard):
        """All peers dead → warnings, empty states."""
        r = dashboard.get("/api/ring-state")
        data = r.json()
        assert data["alive_count"] == 0
        assert len(data["warnings"]) == 2
    
    def test_metrics_returns_zeros(self, dashboard):
        r = dashboard.get("/api/metrics")
        data = r.json()
        assert data["total_messages"] == 0
        assert data["peer_traffic"] == []
    
    def test_query_no_alive_peers(self, dashboard):
        r = dashboard.post("/api/query", json={"query": "test"})
        data = r.json()
        assert data["status"] == "error"
    
    def test_churn_remove_unknown_node(self, dashboard):
        r = dashboard.post("/api/churn/remove", json={"node_id": 999})
        data = r.json()
        assert data["status"] == "error"
    
    def test_data_preview_no_file(self, dashboard):
        r = dashboard.get("/api/data-preview")
        data = r.json()
        assert data["status"] == "error"


# ============================================================
# TEST: Dashboard with data file
# ============================================================

class TestDashboardWithData:
    
    @pytest.fixture
    def dashboard_with_data(self, tmp_path):
        # Create temp data file
        data = [
            {"id": 1, "title": "Story One", "category": "fiction", "content": "Once upon a time there was a brave knight"},
            {"id": 2, "title": "Story Two", "category": "fiction", "content": "The database system crashed unexpectedly"},
            {"id": 3, "title": "Story Three", "category": "tech", "content": "Distributed systems require careful design"},
        ]
        data_file = tmp_path / "test_data.json"
        data_file.write_text(json.dumps(data), encoding="utf-8")
        
        app = create_dashboard_app(
            peers_config={10: "http://127.0.0.1:19901"},
            data_file=str(data_file),
        )
        client = TestClient(app)
        yield client
    
    def test_data_preview(self, dashboard_with_data):
        r = dashboard_with_data.get("/api/data-preview")
        data = r.json()
        assert data["total_docs"] == 3
        assert len(data["sample"]) == 3
    
    def test_publish_all_peers_dead(self, dashboard_with_data):
        """Publish khi peers dead → unreachable nhưng không crash."""
        r = dashboard_with_data.post("/api/setup/publish")
        data = r.json()
        assert data["status"] == "ok"
        assert data["total_docs"] == 3


# ============================================================
# INTEGRATION TEST: Real peer servers
# ============================================================

class TestIntegrationWithRealPeers:
    """
    Integration test: start 3 peer servers thật, test toàn bộ flow.
    
    Flow: register → join → stabilize → publish → query → verify
    
    Đây là AC-8: swap transport, kết quả giống nhau.
    """
    
    @pytest.fixture(autouse=True)
    def setup_real_peers(self):
        """Start 3 peer servers trên ports thật."""
        import threading
        import time
        import uvicorn
        import httpx
        
        from peer_server import create_app
        
        self.ports = {10: 18001, 60: 18002, 110: 18003}
        self.servers = []
        self.threads = []
        
        for node_id, port in self.ports.items():
            app = create_app(node_id=node_id, port=port, m=8)
            config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
            server = uvicorn.Server(config)
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            self.servers.append(server)
            self.threads.append(thread)
        
        # Wait for all servers to be ready
        deadline = time.time() + 10
        for node_id, port in self.ports.items():
            url = f"http://127.0.0.1:{port}/health"
            while time.time() < deadline:
                try:
                    r = httpx.get(url, timeout=1.0)
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(0.1)
        
        yield
        
        # Cleanup
        for server in self.servers:
            server.should_exit = True
        for thread in self.threads:
            thread.join(timeout=3)
    
    def test_full_flow_register_join_stabilize_query(self):
        """
        Integration test: full P2P flow qua HTTP thật.
        
        Chứng minh: Chord routing hoạt động qua NetworkTransport.
        """
        peers_config = {nid: f"http://127.0.0.1:{port}" for nid, port in self.ports.items()}
        app = create_dashboard_app(peers_config=peers_config)
        client = TestClient(app)
        
        # 1. Verify peers alive
        r = client.get("/api/peers")
        alive = [p for p in r.json()["peers"] if p["alive"]]
        assert len(alive) == 3, f"Expected 3 alive peers, got {len(alive)}"
        
        # 2. Register all peers
        r = client.post("/api/setup/register")
        assert r.status_code == 200
        
        # 3. Join ring
        r = client.post("/api/setup/join")
        data = r.json()
        assert data["bootstrap"] == 10
        
        # 4. Stabilize (m=8 rounds)
        r = client.post("/api/setup/stabilize", json={"rounds": 8})
        assert r.status_code == 200
        
        # 5. Verify ring state
        r = client.get("/api/ring-state")
        states = r.json()["states"]
        assert len(states) == 3
        
        # Verify ring topology: mỗi node có successor ≠ self (trừ single-node)
        for nid_str, state in states.items():
            assert state["is_joined"] == True
            assert state["successor"] != state["node_id"] or len(states) == 1
        
        # 6. Publish data
        import httpx
        for nid, port in self.ports.items():
            # Mỗi peer publish 1 keyword
            data = {"system": [1, 2], "database": [2, 3]} if nid == 10 else \
                   {"network": [4, 5]} if nid == 60 else \
                   {"system": [6, 7]}
            r = httpx.post(
                f"http://127.0.0.1:{port}/api/publish",
                json={"data": data},
                timeout=10.0
            )
            assert r.status_code == 200
        
        # 7. Query
        r = client.post("/api/query", json={"query": "system", "initiator_node_id": 10})
        data = r.json()
        assert data["status"] == "ok"
        # "system" published by Node 10 ([1,2]) and Node 110 ([6,7])
        # DHT merge_put → {1,2,6,7}
        result_set = set(data["final_result"])
        assert result_set == {1, 2, 6, 7}, f"Expected {{1,2,6,7}}, got {result_set}"
        
        # 8. Verify metrics
        r = client.get("/api/metrics")
        metrics = r.json()
        assert metrics["total_messages"] > 0
        
        # 9. Verify message log
        r = client.get("/api/messages/all")
        assert r.json()["total_new"] > 0

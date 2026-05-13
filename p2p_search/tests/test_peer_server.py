"""
Test Peer Server — Unit tests cho FastAPI peer endpoints.

Test strategy:
- Dùng FastAPI TestClient (không cần start uvicorn)
- Test từng endpoint riêng lẻ
- Test flow: register → join → stabilize → publish → query → state
- Test error cases

NOTE: TestClient KHÔNG bind real port, nên tests cần Chord routing
(query, publish) phải dùng LocalTransport fixture.
Tests chỉ verify API layer dùng NetworkTransport fixture bình thường.
"""

import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from peer_server import create_app
from src.models import Message
from src.transport import LocalTransport
from src.chord.node import ChordNode


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def single_peer():
    """1 peer duy nhất (bootstrap). Dùng cho tests KHÔNG cần routing."""
    app = create_app(node_id=10, port=8001, m=8)
    client = TestClient(app)
    yield client, app


@pytest.fixture
def routable_peer():
    """
    1 peer có khả năng routing (dùng LocalTransport thay NetworkTransport).
    
    TestClient không bind port thật → NetworkTransport.send() tới chính mình fail.
    Giải pháp: swap transport thành LocalTransport, register node vào transport.
    Cho phép test publish, query trên single-node ring.
    """
    app = create_app(node_id=10, port=8001, m=8)
    
    # Swap transport: NetworkTransport → LocalTransport
    local_transport = LocalTransport()
    node = app.state.node
    node.transport = local_transport
    app.state.transport = local_transport
    
    # Register node vào LocalTransport (tham chiếu trực tiếp object)
    local_transport.register(10, node)
    
    client = TestClient(app)
    yield client, app


# ============================================================
# TEST: Health & Basic Endpoints
# ============================================================

class TestHealth:
    def test_health_returns_ok(self, single_peer):
        client, app = single_peer
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["node_id"] == 10
        assert data["status"] == "ok"
        assert data["is_joined"] == False
        assert data["port"] == 8001


class TestState:
    def test_initial_state(self, single_peer):
        """State trước khi join — mọi thứ trống."""
        client, app = single_peer
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        
        assert data["node_id"] == 10
        assert data["m"] == 8
        assert data["is_joined"] == False
        assert data["successor"] == 10  # chưa join → self
        assert data["predecessor"] is None
        assert data["dht_store"] == {}
        assert data["replica_store"] == {}
        assert data["status"] == "ok"
    
    def test_state_has_finger_table(self, single_peer):
        """Finger table có đúng m entries."""
        client, app = single_peer
        r = client.get("/api/state")
        data = r.json()
        
        assert len(data["finger_table"]) == 8
        for entry in data["finger_table"]:
            assert "index" in entry
            assert "start" in entry
            assert "node" in entry
    
    def test_state_has_stats(self, single_peer):
        """Stats section đầy đủ."""
        client, app = single_peer
        r = client.get("/api/state")
        data = r.json()
        stats = data["stats"]
        
        assert "dht_key_count" in stats
        assert "replica_key_count" in stats
        assert "local_keyword_count" in stats
        assert "message_count" in stats

    def test_state_has_known_peers(self, single_peer):
        """Known peers bao gồm chính nó."""
        client, app = single_peer
        r = client.get("/api/state")
        data = r.json()
        
        assert 10 in data["known_peers"]  # self-registered


# ============================================================
# TEST: Register Peers  
# ============================================================

class TestRegisterPeers:
    def test_register_peers(self, single_peer):
        client, app = single_peer
        r = client.post("/api/register-peers", json={
            "peers": {
                "60": "http://127.0.0.1:8002",
                "110": "http://127.0.0.1:8003",
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert 60 in data["registered"]
        assert 110 in data["registered"]
    
    def test_register_skips_self(self, single_peer):
        """Register không thêm chính mình vào lại."""
        client, app = single_peer
        r = client.post("/api/register-peers", json={
            "peers": {
                "10": "http://127.0.0.1:8001",  # self
                "60": "http://127.0.0.1:8002",
            }
        })
        data = r.json()
        assert 10 not in data["registered"]
        assert 60 in data["registered"]
    
    def test_register_updates_known_peers(self, single_peer):
        client, app = single_peer
        client.post("/api/register-peers", json={
            "peers": {"60": "http://127.0.0.1:8002"}
        })
        
        r = client.get("/api/state")
        data = r.json()
        assert 60 in data["known_peers"]


# ============================================================
# TEST: Join Ring
# ============================================================

class TestJoin:
    def test_bootstrap_join(self, single_peer):
        """Join bằng cách bootstrap (node đầu tiên)."""
        client, app = single_peer
        r = client.post("/api/join", json={"known_node_id": None})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["node_id"] == 10
        # Node tự trỏ successor về mình khi bootstrap
        assert data["successor"] == 10
    
    def test_double_join_rejected(self, single_peer):
        """Join lần 2 trả already_joined."""
        client, app = single_peer
        client.post("/api/join", json={"known_node_id": None})
        r = client.post("/api/join", json={"known_node_id": None})
        data = r.json()
        assert data["status"] == "already_joined"

    def test_is_joined_state_updated(self, single_peer):
        """Sau join, state shows is_joined=True."""
        client, app = single_peer
        client.post("/api/join", json={"known_node_id": None})
        
        r = client.get("/api/state")
        assert r.json()["is_joined"] == True


# ============================================================
# TEST: Stabilize
# ============================================================

class TestStabilize:
    def test_stabilize_runs(self, single_peer):
        """Stabilize chạy không crash (single node)."""
        client, app = single_peer
        client.post("/api/join", json={"known_node_id": None})
        
        r = client.post("/api/stabilize", json={"rounds": 3})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["rounds"] == 3


# ============================================================
# TEST: Receive Message (Chord protocol)
# ============================================================

class TestReceiveMessage:
    def test_ping_message(self, single_peer):
        """POST /message với PING."""
        client, app = single_peer
        msg = Message("PING", sender_id=99).to_dict()
        r = client.post("/message", json=msg)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] == True
    
    def test_get_predecessor_message(self, single_peer):
        """POST /message với GET_PREDECESSOR."""
        client, app = single_peer
        client.post("/api/join", json={"known_node_id": None})
        
        msg = Message("GET_PREDECESSOR", sender_id=99).to_dict()
        r = client.post("/message", json=msg)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] == True
        assert "predecessor" in data["data"]
    
    def test_unknown_message_type(self, single_peer):
        """Message type không hợp lệ → error response."""
        client, app = single_peer
        msg = Message("INVALID_TYPE", sender_id=99).to_dict()
        r = client.post("/message", json=msg)
        data = r.json()
        assert data["success"] == False

    def test_put_and_get_on_single_node(self, single_peer):
        """PUT + GET trên single node ring."""
        client, app = single_peer
        client.post("/api/join", json={"known_node_id": None})
        
        # PUT
        put_msg = Message("PUT", sender_id=10, payload={
            "keyword": "test", "doc_ids": [1, 2, 3]
        }).to_dict()
        r = client.post("/message", json=put_msg)
        assert r.json()["success"] == True
        
        # GET
        get_msg = Message("GET", sender_id=10, payload={
            "keyword": "test"
        }).to_dict()
        r = client.post("/message", json=get_msg)
        data = r.json()
        assert data["success"] == True
        assert set(data["data"]["doc_ids"]) == {1, 2, 3}


# ============================================================
# TEST: Publish
# ============================================================

class TestPublish:
    def test_publish_on_single_node(self, routable_peer):
        """Publish data → DHT store updated (single node, tất cả key thuộc mình)."""
        client, app = routable_peer
        client.post("/api/join", json={"known_node_id": None})
        # Stabilize để finger table đúng
        client.post("/api/stabilize", json={"rounds": 8})
        
        r = client.post("/api/publish", json={
            "data": {
                "system": [1, 2, 5],
                "database": [1, 2, 3],
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "system" in data["keywords_published"]
        
        # Verify state có data
        state = client.get("/api/state").json()
        assert state["stats"]["local_keyword_count"] == 2


# ============================================================
# TEST: Query
# ============================================================

class TestQuery:
    def test_query_on_single_node(self, routable_peer):
        """Query single keyword trên single node."""
        client, app = routable_peer
        client.post("/api/join", json={"known_node_id": None})
        client.post("/api/stabilize", json={"rounds": 8})
        
        # Trực tiếp PUT vào DHT
        put_msg = Message("PUT", sender_id=10, payload={
            "keyword": "system", "doc_ids": [1, 2, 5]
        }).to_dict()
        client.post("/message", json=put_msg)
        
        # Query
        r = client.post("/api/query", json={"query": "system"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert set(data["final_result"]) == {1, 2, 5}
    
    def test_query_empty(self, single_peer):
        """Query rỗng → error."""
        client, app = single_peer
        r = client.post("/api/query", json={"query": ""})
        data = r.json()
        assert data["status"] == "error"

    def test_query_nonexistent_keyword(self, routable_peer):
        """Query keyword không tồn tại → empty result."""
        client, app = routable_peer
        client.post("/api/join", json={"known_node_id": None})
        client.post("/api/stabilize", json={"rounds": 8})
        
        r = client.post("/api/query", json={"query": "nonexistent"})
        data = r.json()
        assert data["final_result"] == []


# ============================================================
# TEST: Messages Log
# ============================================================

class TestMessages:
    def test_messages_initially_empty(self, single_peer):
        client, app = single_peer
        r = client.get("/api/messages")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 0
        assert isinstance(data["entries"], list)
    
    def test_messages_since_pagination(self, single_peer):
        """since param tránh fetch lại log cũ."""
        client, app = single_peer
        # Generate some messages
        client.post("/api/join", json={"known_node_id": None})
        
        # Get all
        r = client.get("/api/messages?since=0")
        total = r.json()["total"]
        
        # Get from middle
        r2 = client.get(f"/api/messages?since={total}")
        assert len(r2.json()["entries"]) == 0
        assert r2.json()["has_more"] == False

"""
Test NetworkTransport — Unit tests + Integration tests.

Test Strategy:
- Unit tests: Mock HTTP server (FastAPI TestClient pattern)
- Test mọi error path: timeout, connection refused, invalid JSON, HTTP 500
- Test happy path: send → receive → parse Response
- Test contract: NetworkTransport phải tuân thủ Transport ABC
- Test message_log: đảm bảo log hoạt động giống LocalTransport
"""

import pytest
import threading
import time
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from src.network_transport import NetworkTransport
from src.transport import Transport, LocalTransport
from src.models import Message, Response, ErrorCode


# ============================================================
# FIXTURES — Mock peer server cho testing
# ============================================================

def create_mock_peer_app(node_id: int = 99, behavior: str = "echo"):
    """
    Tạo FastAPI app giả lập peer server.
    
    Behaviors:
    - "echo": Trả Response(success=True, data=payload)
    - "find_successor": Giả lập FIND_SUCCESSOR → trả successor
    - "slow": Delay 3s trước khi trả lời (test timeout)
    - "error": Trả HTTP 500 
    - "bad_json": Trả response không phải JSON hợp lệ
    """
    app = FastAPI()
    
    @app.post("/message")
    def handle_message(msg: dict):
        if behavior == "echo":
            return Response(
                success=True, 
                data={"echo": msg, "handled_by": node_id}
            ).to_dict()
            
        elif behavior == "find_successor":
            key = msg.get("payload", {}).get("key", 0)
            return Response(
                success=True,
                data={
                    "successor": node_id,
                    "path": [{
                        "node": node_id,
                        "action": "RESOLVED",
                        "target_key": key,
                        "next_node": node_id,
                        "reason": f"mock: key {key} resolved at N{node_id}"
                    }]
                }
            ).to_dict()
            
        elif behavior == "slow":
            time.sleep(3)
            return Response(success=True, data={"slow": True}).to_dict()
            
        elif behavior == "error":
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"}
            )
            
        elif behavior == "bad_json":
            from starlette.responses import PlainTextResponse
            return PlainTextResponse("this is not json{{{")
    
    @app.get("/health")
    def health():
        return {"node_id": node_id, "status": "ok"}
    
    return app


class MockPeerServer:
    """
    Chạy FastAPI mock server trong background thread.
    Dùng trong tests để giả lập peer server thực.
    """
    def __init__(self, app: FastAPI, host: str = "127.0.0.1", port: int = 0):
        self.app = app
        self.host = host
        self.port = port or self._find_free_port()
        self.server = None
        self.thread = None
        self.url = f"http://{self.host}:{self.port}"
        
    @staticmethod
    def _find_free_port():
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    def start(self, timeout: float = 5.0):
        """Start server in background thread, wait until ready."""
        config = uvicorn.Config(
            self.app, 
            host=self.host, 
            port=self.port, 
            log_level="warning",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        
        # Wait cho server ready
        import httpx
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(f"{self.url}/health", timeout=1.0)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"Mock server failed to start on {self.url}")
    
    def stop(self):
        if self.server:
            self.server.should_exit = True
            if self.thread:
                self.thread.join(timeout=3)


# ============================================================
# TEST: Transport ABC Contract
# ============================================================

class TestTransportContract:
    """Verify NetworkTransport tuân thủ Transport ABC."""
    
    def test_is_subclass_of_transport(self):
        assert issubclass(NetworkTransport, Transport)
    
    def test_has_send_method(self):
        transport = NetworkTransport()
        assert hasattr(transport, 'send')
        assert callable(transport.send)
        transport.close()
    
    def test_has_register_unregister(self):
        transport = NetworkTransport()
        assert hasattr(transport, 'register')
        assert hasattr(transport, 'unregister')
        transport.close()
    
    def test_has_message_log(self):
        transport = NetworkTransport()
        assert hasattr(transport, 'message_log')
        assert isinstance(transport.message_log, list)
        transport.close()
    
    def test_registry_starts_empty(self):
        transport = NetworkTransport()
        assert transport.registry == {}
        transport.close()

    def test_register_stores_url(self):
        transport = NetworkTransport()
        transport.register(10, "http://127.0.0.1:8001")
        assert 10 in transport.registry
        assert transport.registry[10] == "http://127.0.0.1:8001"
        transport.close()
    
    def test_unregister_removes_url(self):
        transport = NetworkTransport()
        transport.register(10, "http://127.0.0.1:8001")
        transport.unregister(10)
        assert 10 not in transport.registry
        transport.close()
    
    def test_context_manager(self):
        with NetworkTransport() as transport:
            transport.register(10, "http://127.0.0.1:8001")
            assert 10 in transport.registry
        # Client should be closed after exiting context


# ============================================================
# TEST: Error Handling — Không cần server chạy
# ============================================================

class TestErrorHandlingNoServer:
    """Test error paths mà không cần mock server."""
    
    def test_send_to_unregistered_node_returns_not_found(self):
        """Node không trong registry → NODE_NOT_FOUND."""
        with NetworkTransport() as transport:
            msg = Message("PING", sender_id=1)
            response = transport.send(999, msg)
            
            assert not response.success
            assert response.error == ErrorCode.NODE_NOT_FOUND
    
    def test_send_to_dead_server_returns_unreachable(self):
        """Server không chạy → NODE_UNREACHABLE."""
        with NetworkTransport() as transport:
            # Register URL mà không có server nào chạy
            transport.register(10, "http://127.0.0.1:19999")
            msg = Message("PING", sender_id=1)
            response = transport.send(10, msg)
            
            assert not response.success
            assert response.error == ErrorCode.NODE_UNREACHABLE
    
    def test_message_log_records_even_on_failure(self):
        """Message log ghi lại kể cả khi send fail."""
        with NetworkTransport() as transport:
            msg = Message("PING", sender_id=1)
            transport.send(999, msg)  # NODE_NOT_FOUND
            
            assert len(transport.message_log) == 1
            assert transport.message_log[0]["type"] == "PING"
            assert transport.message_log[0]["from"] == 1
            assert transport.message_log[0]["to"] == 999

    def test_message_log_records_connection_failure(self):
        """Message log ghi lại khi connection refused."""
        with NetworkTransport() as transport:
            transport.register(10, "http://127.0.0.1:19999")
            msg = Message("FIND_SUCCESSOR", sender_id=1, payload={"key": 50})
            transport.send(10, msg)
            
            assert len(transport.message_log) == 1
            assert transport.message_log[0]["type"] == "FIND_SUCCESSOR"


# ============================================================
# TEST: Happy Path — Cần mock server
# ============================================================

class TestHappyPath:
    """Test send thành công qua HTTP."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self):
        """Start mock echo server."""
        app = create_mock_peer_app(node_id=99, behavior="echo")
        self.server = MockPeerServer(app)
        self.server.start()
        yield
        self.server.stop()
    
    def test_send_ping_success(self):
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("PING", sender_id=1)
            response = transport.send(99, msg)
            
            assert response.success
            assert response.data["handled_by"] == 99
    
    def test_send_find_successor_message(self):
        """Gửi FIND_SUCCESSOR message qua HTTP, verify payload round-trip."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("FIND_SUCCESSOR", sender_id=10, payload={"key": 73}, ttl=20)
            response = transport.send(99, msg)
            
            assert response.success
            echo = response.data["echo"]
            assert echo["type"] == "FIND_SUCCESSOR"
            assert echo["sender_id"] == 10
            assert echo["payload"]["key"] == 73
            assert echo["ttl"] == 20
    
    def test_send_put_message(self):
        """PUT message với doc_ids list."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("PUT", sender_id=10, payload={
                "keyword": "system", 
                "doc_ids": [1, 2, 5]
            })
            response = transport.send(99, msg)
            
            assert response.success
            echo = response.data["echo"]
            assert echo["payload"]["keyword"] == "system"
            assert echo["payload"]["doc_ids"] == [1, 2, 5]
    
    def test_message_log_on_success(self):
        """Message log ghi lại khi send thành công."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("PING", sender_id=1)
            transport.send(99, msg)
            
            assert len(transport.message_log) == 1
            log_entry = transport.message_log[0]
            assert log_entry["from"] == 1
            assert log_entry["to"] == 99
            assert log_entry["type"] == "PING"
            assert "timestamp" in log_entry

    def test_multiple_sends_accumulate_log(self):
        """Nhiều send → log tích lũy."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            for i in range(5):
                transport.send(99, Message("PING", sender_id=i))
            
            assert len(transport.message_log) == 5


# ============================================================
# TEST: FIND_SUCCESSOR Mock
# ============================================================

class TestFindSuccessorMock:
    """Test với mock server giả lập FIND_SUCCESSOR handler."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self):
        app = create_mock_peer_app(node_id=110, behavior="find_successor")
        self.server = MockPeerServer(app)
        self.server.start()
        yield
        self.server.stop()
    
    def test_find_successor_returns_correct_data(self):
        with NetworkTransport() as transport:
            transport.register(110, self.server.url)
            msg = Message("FIND_SUCCESSOR", sender_id=10, payload={"key": 73})
            response = transport.send(110, msg)
            
            assert response.success
            assert response.data["successor"] == 110
            assert len(response.data["path"]) == 1
            assert response.data["path"][0]["action"] == "RESOLVED"


# ============================================================
# TEST: Timeout
# ============================================================

class TestTimeout:
    """Test timeout handling."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self):
        app = create_mock_peer_app(node_id=99, behavior="slow")
        self.server = MockPeerServer(app)
        self.server.start()
        yield
        self.server.stop()
    
    def test_timeout_returns_timeout_error(self):
        """Server chậm + timeout ngắn → TIMEOUT error."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("PING", sender_id=1)
            # Timeout 500ms, server delay 3s → timeout
            response = transport.send(99, msg, timeout_ms=500)
            
            assert not response.success
            assert response.error == ErrorCode.TIMEOUT


# ============================================================
# TEST: HTTP 500 Error
# ============================================================

class TestServerError:
    """Test HTTP 500 handling."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self):
        app = create_mock_peer_app(node_id=99, behavior="error")
        self.server = MockPeerServer(app)
        self.server.start()
        yield
        self.server.stop()
    
    def test_http_500_returns_unreachable(self):
        """Server trả 500 → NODE_UNREACHABLE."""
        with NetworkTransport() as transport:
            transport.register(99, self.server.url)
            msg = Message("PING", sender_id=1)
            response = transport.send(99, msg)
            
            assert not response.success
            assert response.error == ErrorCode.NODE_UNREACHABLE
            assert response.data.get("http_status") == 500


# ============================================================
# TEST: Multi-peer scenario  
# ============================================================

class TestMultiPeer:
    """Test gửi message tới nhiều peers khác nhau."""
    
    @pytest.fixture(autouse=True)
    def setup_servers(self):
        app1 = create_mock_peer_app(node_id=10, behavior="echo")
        app2 = create_mock_peer_app(node_id=60, behavior="echo")
        
        self.server1 = MockPeerServer(app1)
        self.server2 = MockPeerServer(app2)
        self.server1.start()
        self.server2.start()
        yield
        self.server1.stop()
        self.server2.stop()
    
    def test_send_to_different_peers(self):
        with NetworkTransport() as transport:
            transport.register(10, self.server1.url)
            transport.register(60, self.server2.url)
            
            r1 = transport.send(10, Message("PING", sender_id=0))
            r2 = transport.send(60, Message("PING", sender_id=0))
            
            assert r1.success
            assert r2.success
            assert r1.data["handled_by"] == 10
            assert r2.data["handled_by"] == 60
    
    def test_unregister_peer_then_send_fails(self):
        """Unregister peer → send tới nó fail với NODE_NOT_FOUND."""
        with NetworkTransport() as transport:
            transport.register(10, self.server1.url)
            transport.register(60, self.server2.url)
            
            # Send thành công
            r1 = transport.send(10, Message("PING", sender_id=0))
            assert r1.success
            
            # Unregister
            transport.unregister(10)
            
            # Send fail
            r2 = transport.send(10, Message("PING", sender_id=0))
            assert not r2.success
            assert r2.error == ErrorCode.NODE_NOT_FOUND
            
            # Peer 60 vẫn OK
            r3 = transport.send(60, Message("PING", sender_id=0))
            assert r3.success


# ============================================================
# TEST: Behavioral Parity với LocalTransport
# ============================================================

class TestParityWithLocalTransport:
    """
    Kiểm chứng NetworkTransport trả kết quả tương đương LocalTransport
    cho cùng scenario.
    """
    
    def test_node_not_found_parity(self):
        """Cả 2 transport đều trả NODE_NOT_FOUND cho node không tồn tại."""
        local = LocalTransport()
        network = NetworkTransport()
        
        msg = Message("PING", sender_id=1)
        
        local_resp = local.send(999, msg)
        network_resp = network.send(999, msg)
        
        assert local_resp.success == network_resp.success == False
        assert local_resp.error == network_resp.error == ErrorCode.NODE_NOT_FOUND
        
        network.close()
    
    def test_message_log_format_parity(self):
        """Cả 2 transport đều log cùng format."""
        local = LocalTransport()
        network = NetworkTransport()
        
        msg = Message("FIND_SUCCESSOR", sender_id=10, payload={"key": 73})
        
        local.send(999, msg)   # sẽ fail nhưng vẫn log
        network.send(999, msg) # sẽ fail nhưng vẫn log
        
        local_log = local.message_log[0]
        network_log = network.message_log[0]
        
        # Cùng fields
        assert local_log["from"] == network_log["from"] == 10
        assert local_log["to"] == network_log["to"] == 999
        assert local_log["type"] == network_log["type"] == "FIND_SUCCESSOR"
        assert "timestamp" in local_log
        assert "timestamp" in network_log
        
        network.close()

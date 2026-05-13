"""
NetworkTransport — HTTP-based transport cho Chord DHT.

Thay thế LocalTransport: mỗi `send()` = HTTP POST tới peer server.
registry: node_id → URL string (e.g., "http://127.0.0.1:8001")

Design decisions:
- httpx.Client sync: giữ nguyên Transport.send() sync interface
- Connection pooling: 1 Client shared, tránh tạo connection mỗi lần send
- Error mapping rõ ràng: httpx exceptions → ErrorCode chuẩn hóa
- Timeout: map timeout_ms param → httpx timeout (seconds)
"""

import logging
import atexit
import httpx

from .transport import Transport
from .models import Message, Response, ErrorCode

logger = logging.getLogger(__name__)


class NetworkTransport(Transport):
    """
    HTTP-based P2P transport.
    
    registry: {node_id: "http://127.0.0.1:{port}"}
    send():   HTTP POST → {url}/message with JSON body
    """

    # Timeout mặc định cho connect (tách riêng khỏi read timeout)
    DEFAULT_CONNECT_TIMEOUT = 5.0  # seconds
    
    def __init__(self, connect_timeout: float = None):
        super().__init__()
        self._connect_timeout = connect_timeout or self.DEFAULT_CONNECT_TIMEOUT
        self._client: httpx.Client = self._create_client()
        # Đảm bảo cleanup khi process exit
        atexit.register(self._cleanup)

    def _create_client(self) -> httpx.Client:
        """Tạo httpx Client với connection pooling."""
        return httpx.Client(
            # Timeout mặc định — sẽ bị override theo timeout_ms ở send()
            timeout=httpx.Timeout(
                connect=self._connect_timeout,
                read=10.0,
                write=5.0,
                pool=5.0,
            ),
            # Connection pool limits hợp lý cho demo (5-10 peers)
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
            ),
            # Không follow redirects — peer-to-peer direct
            follow_redirects=False,
        )

    def send(self, to_node_id: int, message: Message, timeout_ms: int = 5000) -> Response:
        """
        Gửi message tới peer qua HTTP POST.
        
        Flow:
        1. Log message (kế thừa từ Transport)
        2. Check registry
        3. HTTP POST /message với JSON body
        4. Parse response → Response object
        
        Error handling:
        - Node không trong registry → NODE_NOT_FOUND
        - Connection refused/DNS fail → NODE_UNREACHABLE  
        - Timeout → TIMEOUT
        - HTTP 4xx/5xx → NODE_UNREACHABLE (peer có vấn đề)
        - JSON parse error → NODE_UNREACHABLE
        """
        # 1. Ghi log (metrics sử dụng)
        self._log_message(to_node_id, message)
        
        # 2. Kiểm tra registry
        if to_node_id not in self.registry:
            logger.debug(f"Node {to_node_id} not in registry")
            return Response(
                success=False,
                error=ErrorCode.NODE_NOT_FOUND,
                data={}
            )
        
        # 3. Build request
        base_url = self.registry[to_node_id]
        url = f"{base_url}/message"
        payload = message.to_dict()
        
        # 4. HTTP POST với timeout từ parameter
        read_timeout = timeout_ms / 1000.0
        
        try:
            http_response = self._client.post(
                url,
                json=payload,
                timeout=httpx.Timeout(
                    connect=self._connect_timeout,
                    read=read_timeout,
                    write=5.0,
                    pool=5.0,
                ),
            )
            
            # 5xx / 4xx → peer có vấn đề nội bộ
            if http_response.status_code >= 500:
                logger.warning(
                    f"Peer {to_node_id} returned HTTP {http_response.status_code}: "
                    f"{http_response.text[:200]}"
                )
                return Response(
                    success=False,
                    error=ErrorCode.NODE_UNREACHABLE,
                    data={"http_status": http_response.status_code}
                )
            
            if http_response.status_code >= 400:
                logger.warning(
                    f"Peer {to_node_id} rejected request HTTP {http_response.status_code}: "
                    f"{http_response.text[:200]}"
                )
                return Response(
                    success=False,
                    error=ErrorCode.NODE_UNREACHABLE,
                    data={"http_status": http_response.status_code}
                )
            
            # Parse response JSON → Response object
            response_data = http_response.json()
            return Response.from_dict(response_data)
            
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout sending to Node {to_node_id} at {url}: {e}")
            return Response(
                success=False,
                error=ErrorCode.TIMEOUT,
                data={"details": str(e), "timeout_ms": timeout_ms}
            )
            
        except httpx.ConnectError as e:
            logger.warning(f"Connection refused to Node {to_node_id} at {url}: {e}")
            return Response(
                success=False,
                error=ErrorCode.NODE_UNREACHABLE,
                data={"details": str(e)}
            )
            
        except httpx.HTTPError as e:
            # Catch-all cho các HTTP errors khác (DNS, SSL, etc.)
            logger.error(f"HTTP error sending to Node {to_node_id} at {url}: {e}")
            return Response(
                success=False,
                error=ErrorCode.NODE_UNREACHABLE,
                data={"details": str(e)}
            )
            
        except ValueError as e:
            # JSON decode error
            logger.error(f"Invalid JSON response from Node {to_node_id}: {e}")
            return Response(
                success=False,
                error=ErrorCode.NODE_UNREACHABLE,
                data={"details": f"Invalid JSON response: {e}"}
            )

    def close(self):
        """Đóng HTTP client, giải phóng connection pool."""
        if self._client and not self._client.is_closed:
            self._client.close()
            logger.debug("NetworkTransport client closed")

    def _cleanup(self):
        """Cleanup khi process exit — gọi bởi atexit."""
        try:
            self.close()
        except Exception:
            pass  # Swallow errors during cleanup

    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        peers = list(self.registry.keys())
        return f"NetworkTransport(peers={peers})"

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .models import Message, Response, ErrorCode
import logging

class Transport(ABC):
    """
    Interface giao tiếp giữa các peer.
    Chord logic sử dụng interface này để gọi send() mà không cần biết bên dưới là Local hay Network.
    """
    def __init__(self):
        self.registry: Dict[int, Any] = {}          # node_id -> address (hoặc object)
        self.message_log: List[Dict[str, Any]] = [] # MỚI: {"to": to_node_id, "message": message}

    @abstractmethod
    def send(self, to_node_id: int, message: Message, timeout_ms: int = 5000) -> Response:
        """Gửi message tới một node cụ thể."""
        pass

    def register(self, node_id: int, address: Any):
        """Đăng ký peer vào registry."""
        self.registry[node_id] = address

    def unregister(self, node_id: int):
        """Xóa peer khỏi registry (quá trình mạng biến động, node chết / leave)."""
        if node_id in self.registry:
            del self.registry[node_id]

class LocalTransport(Transport):
    """
    Peers giao tiếp bằng function call truyền thống (Simulated local environment).
    registry: node_id -> ChordNode object reference
    """
    def send(self, to_node_id: int, message: Message, timeout_ms: int = 5000) -> Response:
        # Ghi log message để phân tích later (Bổ sung receiver_id để hỗ trợ vẽ đường Hops)
        self.message_log.append({
            "to": to_node_id,
            "message": message
        })
        
        # Mô phỏng rớt mạng: target không tồn tại
        if to_node_id not in self.registry:
            return Response(
                success=False,
                error=ErrorCode.NODE_NOT_FOUND,
                data={}
            )
            
        target_node = self.registry[to_node_id]
        
        # Mô phỏng gọi remote function không bao giờ nên văng exception làm chết chương trình
        try:
            # target_node.handle_message is expected to return a Response object
            return target_node.handle_message(message)
        except Exception as e:
            logging.error(f"Error calling handle_message on node {to_node_id}: {e}")
            return Response(
                success=False,
                error=ErrorCode.NODE_UNREACHABLE,
                data={"details": str(e)}
            )

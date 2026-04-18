from src.models import Message, Response, ErrorCode
import logging

class DispatcherMixin:
    """
    Mixin xử lý luồng Dispatch Message từ Transport chuyển xuống.
    Biến ChordNode thành một Central Switch rẽ nhánh logic.
    """
    def handle_message(self, message: Message) -> Response:
        handlers = {
            "FIND_SUCCESSOR": self._handle_find_successor,
            "GET_PREDECESSOR": self._handle_get_predecessor,
            "NOTIFY": self._handle_notify,
            "PUT": self._handle_put,
            "GET": self._handle_get,
            "STORE_REPLICA": self._handle_store_replica,
            "TRANSFER_KEYS": self._handle_transfer_keys,
            "PING": self._handle_ping
        }
        
        handler = handlers.get(message.type)
        if not handler:
            return Response(
                success=False, 
                error=ErrorCode.UNKNOWN_TYPE, 
                data={"type": message.type}
            )
            
        try:
            return handler(message)
        except Exception as e:
            logging.error(f"Error handling message {message.type} at node {getattr(self, 'node_id', 'unknown')}: {e}")
            return Response(
                success=False, 
                error=ErrorCode.ROUTING_FAILED, 
                data={"details": str(e)}
            )

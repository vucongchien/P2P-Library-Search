from typing import List, Optional, Set, Dict
from src.transport import Transport
from src.models import Message, ErrorCode, Response, RoutingTrace

from .dispatcher_mixin import DispatcherMixin
from .routing_mixin import RoutingMixin
from .storage_mixin import StorageMixin
from .utils import deterministic_hash

class ChordNode(DispatcherMixin, RoutingMixin, StorageMixin):
    """
    Điểm truy cập chính đại diện cho Một Peer trong mạng bằng cách 
    kế thừa (Composition Mixins) chia các file logic rõ ràng.
    """
    def __init__(self, node_id: int, transport: Transport, m: int = 8):
        self.node_id = node_id
        self.m = m
        self.transport = transport
        
        # === Mạng Routing Initial State ===
        self.successor_id = node_id
        self.successor_list: List[int] = [node_id]  # Khởi tạo với chính mình
        self.predecessor_id = None
        self.finger_table: List[Optional[int]] = [None] * m
        self.next_finger_to_fix = 0
        
        # === Mạng Storage Initial State ===
        self.dht_store: Dict[str, Set[int]] = {}
        self.replica_store: Dict[str, Set[int]] = {}
        self.content_store: Dict[int, dict] = {}
        self.replica_content_store: Dict[int, dict] = {}
        
        # === Local Node State ===
        self.local_index: Dict[str, Set[int]] = {}

    def put(self, keyword: str, doc_ids: Set[int]) -> bool:
        """API Công Khai để đẩy chỉ mục Index vào DHT."""
        # 1. Băm từ khóa thành key ID
        key_id = deterministic_hash(keyword, self.m)
        
        # 2. Tìm Node đang chịu trách nhiệm giữ khóa này (có trace)
        trace = self.find_successor_traced(key_id)
        
        if not trace.success:
            print(f"[Warning] Routing failed for '{keyword}' (key={key_id})")
            return False
        
        # 3. Gửi thông điệp PUT thông qua Mạng
        response = self.transport.send(
            trace.target_id, 
            Message("PUT", self.node_id, {"keyword": keyword, "doc_ids": list(doc_ids)})
        )
        if not response.success:
            print(f"[Warning] Failed to put '{keyword}' to Node {trace.target_id}. Reason: {response.error}")
            return False
            
        return True

    def put_content(self, doc_id: int, content: dict) -> bool:
        """API Công Khai để đẩy nội dung Document vào DHT."""
        key_id = deterministic_hash(str(doc_id), self.m)
        trace = self.find_successor_traced(key_id)
        
        if not trace.success:
            print(f"[Warning] Routing failed for document content '{doc_id}' (key={key_id})")
            return False
            
        response = self.transport.send(
            trace.target_id,
            Message("PUT_CONTENT", self.node_id, {"doc_id": doc_id, "content": content})
        )
        if not response.success:
            print(f"[Warning] Failed to put content '{doc_id}' to Node {trace.target_id}. Reason: {response.error}")
            return False
            
        return True

    def get(self, keyword: str) -> Response:
        """
        API Công Khai để đọc chỉ mục từ DHT phục vụ tìm kiếm.
        
        Response.data bao gồm:
          - keyword: str
          - doc_ids: List[int]  
          - routing_trace: dict  ← TRACE THẬT từ routing
        """
        key_id = deterministic_hash(keyword, self.m)
        trace = self.find_successor_traced(key_id)
        
        if not trace.success:
            return Response(
                success=False,
                error=ErrorCode.ROUTING_FAILED,
                data={"keyword": keyword, "routing_trace": trace.to_dict()}
            )
        
        response = self.transport.send(
             trace.target_id,
             Message("GET", self.node_id, {"keyword": keyword})
        )
        
        # Gắn routing trace vào response — source of truth
        if response.data is None:
            response.data = {}
        response.data["routing_trace"] = trace.to_dict()
        
        return response

    def get_content(self, doc_id: int) -> Response:
        """API Công Khai để đọc thân tài liệu từ DHT."""
        key_id = deterministic_hash(str(doc_id), self.m)
        trace = self.find_successor_traced(key_id)
        
        if not trace.success:
            return Response(
                success=False,
                error=ErrorCode.ROUTING_FAILED,
                data={"doc_id": doc_id, "routing_trace": trace.to_dict()}
            )
            
        response = self.transport.send(
             trace.target_id,
             Message("GET_CONTENT", self.node_id, {"doc_id": doc_id})
        )
        
        if response.data is None:
            response.data = {}
        response.data["routing_trace"] = trace.to_dict()
        
        return response

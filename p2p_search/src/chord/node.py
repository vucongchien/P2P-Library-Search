from typing import List, Optional, Set, Dict
from src.transport import Transport
from src.models import Message, ErrorCode

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
        self.predecessor_id = None
        self.finger_table: List[Optional[int]] = [None] * m
        self.next_finger_to_fix = 0
        
        # === Mạng Storage Initial State ===
        self.dht_store: Dict[str, Set[int]] = {}
        self.replica_store: Dict[str, Set[int]] = {}

    def put(self, keyword: str, doc_ids: Set[int]) -> bool:
        """API Công Khai để đẩy chỉ mục Index vào DHT."""
        # 1. Băm từ khóa thành key ID
        key_id = deterministic_hash(keyword, self.m)
        
        # 2. Tìm Node đang chịu trách nhiệm giữ khóa này
        target_node = self.find_successor(key_id)
        
        # 3. Gửi thông điệp PUT thông qua Mạng thay vì tự làm
        response = self.transport.send(
            target_node, 
            Message("PUT", self.node_id, {"keyword": keyword, "doc_ids": list(doc_ids)})
        )
        if not response.success:
            print(f"[Warning] Failed to put '{keyword}' to Node {target_node}. Reason: {response.error}")
            return False
            
        return True

    def get(self, keyword: str) -> Set[int]:
        """API Công Khai để đọc chỉ mục từ DHT phục vụ tìm kiếm."""
        key_id = deterministic_hash(keyword, self.m)
        target_node = self.find_successor(key_id)
        
        response = self.transport.send(
             target_node,
             Message("GET", self.node_id, {"keyword": keyword})
        )
        
        if not response.success:
            # DHT có thể bị lỗi truy xuất nhất thời
            if response.error == ErrorCode.NODE_UNREACHABLE:
                print(f"[Warning] Node {target_node} unreachable, data for '{keyword}' might be missed.")
            return set()
            
        return set(response.data.get("doc_ids", []))

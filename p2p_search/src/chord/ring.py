from typing import Dict, List, Optional
from .node import ChordNode
from ..transport import Transport
from ..models import Message

class ChordRing:
    """
    Quản lý vòng mạng Chord giả lập. 
    Chịu trách nhiệm khởi tạo, thêm/xóa node và điều phối quá trình ổn định mạng (stabilization).
    """
    def __init__(self, transport: Transport, m: int = 8):
        self.transport = transport
        self.m = m
        self.nodes: Dict[int, ChordNode] = {}
        
    def add_node(self, node_id: int) -> ChordNode:
        """Thêm một node mới vào vòng mạng."""
        if node_id in self.nodes:
            raise ValueError(f"Node ID {node_id} already exists in the ring.")
            
        new_node = ChordNode(node_id, self.transport, self.m)
        
        # Nếu đã có node trong mạng, cho node mới join thông qua một node bất kỳ
        known_node_id = next(iter(self.nodes.keys())) if self.nodes else None
        
        # Đăng ký node vào transport trước khi join để có thể nhận tin nhắn
        self.transport.register(node_id, new_node)
        
        # Thực hiện Join logic (tìm successor)
        new_node.join(known_node_id)
        
        self.nodes[node_id] = new_node
        return new_node

    def remove_node(self, node_id: int):
        """Xóa một node khỏi vòng mạng (giả lập churn)."""
        if node_id in self.nodes:
            self.transport.unregister(node_id)
            del self.nodes[node_id]

    def stabilize_all(self, rounds: int = 3):
        """
        Chạy quá trình ổn định cho toàn bộ các node trong mạng.
        Trong thực tế điều này chạy định kỳ/bất đồng bộ trên mỗi node.
        """
        import random
        for _ in range(rounds):
            nodes = list(self.nodes.values())
            random.shuffle(nodes)  # Phá bỏ bias do thứ tự insertion
            
            # Thứ tự gọi quan trọng: stabilize -> fix_fingers -> check_predecessor
            for node in nodes:
                node.stabilize()
            for node in nodes:
                node.fix_fingers()
            for node in nodes:
                node.check_predecessor()

    def get_node(self, node_id: int) -> Optional[ChordNode]:
        return self.nodes.get(node_id)

    @classmethod
    def create(cls, node_ids: List[int], transport: Transport, m: int = 8) -> 'ChordRing':
        """Tiện ích khởi tạo nhanh một cụm node."""
        ring = cls(transport, m)
        for nid in node_ids:
            ring.add_node(nid)
        
        # Chạy m vòng để đảm bảo toàn bộ finger table (m mục) được cập nhật ít nhất 1 lần
        ring.stabilize_all(rounds=m)
        return ring

from typing import Dict, Set, List
from src.models import Message, Response
from .utils import deterministic_hash, in_range

class StorageMixin:
    """
    Mixin đảm nhiệm lưu trữ Key-Value kiểu P2P (DHT),
    ở đây Map cụ thể Keyword -> Set[DocID] cho Search Engine.
    """
    dht_store: Dict[str, Set[int]]
    replica_store: Dict[str, Set[int]]

    def _handle_put(self, message: Message) -> Response:
        """Nhận Keyword và đính kèm danh sách tài liệu vào kho. Dùng Union không dùng Overwrite."""
        payload = message.payload
        keyword = payload["keyword"]
        doc_ids_list = payload["doc_ids"]

        if keyword not in self.dht_store:
            self.dht_store[keyword] = set()

        # Merge Put bằng thuật toán Union Set
        self.dht_store[keyword].update(doc_ids_list)
        
        # Sao chép dữ liệu dự phòng sang Successor (Replication)
        if getattr(self, "successor_id", None) is not None and getattr(self, "node_id", None) is not None:
            if self.successor_id != self.node_id:
                self.transport.send(
                    self.successor_id,
                    Message("STORE_REPLICA", self.node_id, {"keyword": keyword, "doc_ids": doc_ids_list})
                )

        return Response(success=True)

    def _handle_get(self, message: Message) -> Response:
        """Truy xuất keyword."""
        payload = message.payload
        keyword = payload["keyword"]
        
        # Lấy từ kho. Nếu không có thì trả về Set rỗng [] - Đây không phải Error
        doc_ids = self.dht_store.get(keyword, set())
        return Response(success=True, data={"keyword": keyword, "doc_ids": list(doc_ids)})

    def _handle_store_replica(self, message: Message) -> Response:
        """Node Predecessor gửi backup data sang cho mình giữ giùm."""
        payload = message.payload
        keyword = payload["keyword"]
        doc_ids_list = payload["doc_ids"]

        if keyword not in self.replica_store:
            self.replica_store[keyword] = set()

        self.replica_store[keyword].update(doc_ids_list)
        return Response(success=True)

    def _transfer_keys_to_predecessor(self, new_predecessor_id: int, old_predecessor_id):
        """
        Data Handoff: Khi có predecessor mới (node vừa join), kiểm tra dht_store
        và chuyển giao các key thuộc phạm vi quản lý của predecessor mới.
        
        Logic: Node S có predecessor thay đổi từ P_old sang N.
        - Trước: S quản lý keys trong (P_old, S]
        - Sau:   S quản lý keys trong (N, S]
        - Vậy keys trong (P_old, N] phải chuyển cho N.
        """
        if not self.dht_store:
            return
        
        keys_to_transfer: Dict[str, List[int]] = {}
        keys_to_remove: List[str] = []
        
        for keyword, doc_ids in self.dht_store.items():
            key_id = deterministic_hash(keyword, self.m)
            
            # Key thuộc về predecessor mới nếu key_id ∈ (old_predecessor, new_predecessor]
            # Trường hợp đặc biệt: old_predecessor là None (node đang bootstrap)
            # -> Chuyển tất cả key có key_id ∈ (new_predecessor+1...trở về trước self) cho new_predecessor
            should_transfer = False
            
            if old_predecessor_id is None or old_predecessor_id == self.node_id:
                # Node đang từ trạng thái cô đơn -> có bạn mới
                # Chuyển key nếu key KHÔNG thuộc (new_predecessor, self]
                if not in_range(key_id, new_predecessor_id, self.node_id, inclusive_left=False, inclusive_right=True):
                    should_transfer = True
            else:
                # Chuyển key nếu key ∈ (old_predecessor, new_predecessor]
                if in_range(key_id, old_predecessor_id, new_predecessor_id, inclusive_left=False, inclusive_right=True):
                    should_transfer = True
            
            if should_transfer:
                keys_to_transfer[keyword] = list(doc_ids)
                keys_to_remove.append(keyword)
        
        if not keys_to_transfer:
            return
        
        # Gửi toàn bộ dữ liệu cho predecessor mới (bulk transfer)
        response = self.transport.send(
            new_predecessor_id,
            Message("TRANSFER_KEYS", self.node_id, {"keys": keys_to_transfer})
        )
        
        # Chỉ xóa dữ liệu nếu chuyển giao thành công
        if response.success:
            for keyword in keys_to_remove:
                del self.dht_store[keyword]

    def _handle_transfer_keys(self, message: Message) -> Response:
        """Nhận bàn giao dữ liệu từ successor khi mình vừa join vào mạng."""
        payload = message.payload
        keys_data = payload.get("keys", {})
        
        for keyword, doc_ids_list in keys_data.items():
            if keyword not in self.dht_store:
                self.dht_store[keyword] = set()
            self.dht_store[keyword].update(doc_ids_list)
        
        return Response(success=True)


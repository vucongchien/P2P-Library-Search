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
    content_store: Dict[int, dict]
    replica_content_store: Dict[int, dict]
    local_index: Dict[str, Set[int]] # (new) local state

    def load_local_index(self, index_data: Dict[str, List[int]]):
        """
        Nạp dữ liệu từ kho lưu trữ Local (giả lập việc quét ổ cứng).
        Đảm bảo Node có nhận thức độc lập về dữ liệu của mình.
        """
        if not hasattr(self, 'local_index'):
             self.local_index = {}
             
        for keyword, doc_ids in index_data.items():
            if keyword not in self.local_index:
                self.local_index[keyword] = set()
            self.local_index[keyword].update(doc_ids)

    def publish(self):
        """
        Node tự nguyện kết nối vào mạng DHT và đẩy thông tin Local Index lên.
        Giúp định hình mạng P2P hoàn toàn tự trị.
        """
        if not hasattr(self, 'local_index'):
            return

        for keyword, doc_ids in self.local_index.items():
            # Tận dụng hàm self.put (có sẵn ở lớp chính ChordNode)
            getattr(self, 'put')(keyword, doc_ids)

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

    def _handle_put_content(self, message: Message) -> Response:
        """Lưu nội dung document vào DHT."""
        payload = message.payload
        doc_id = payload["doc_id"]
        content = payload["content"]
        
        self.content_store[doc_id] = content
        
        if getattr(self, "successor_id", None) is not None and getattr(self, "node_id", None) is not None:
            if self.successor_id != self.node_id:
                self.transport.send(
                    self.successor_id,
                    Message("STORE_CONTENT_REPLICA", self.node_id, {"doc_id": doc_id, "content": content})
                )
                
        return Response(success=True)

    def _promote_replicas(self):
        """
        Data Promotion: Đưa toàn bộ data từ Replica lên Primary.
        Gọi khi phát hiện Predecessor chết.
        """
        promoted_dht = 0
        promoted_content = 0
        
        # Promote DHT Index
        for keyword, doc_ids in self.replica_store.items():
            if keyword not in self.dht_store:
                self.dht_store[keyword] = set()
            self.dht_store[keyword].update(doc_ids)
            promoted_dht += 1
            
        # Promote Content Store
        for doc_id, content in self.replica_content_store.items():
            self.content_store[doc_id] = content
            promoted_content += 1
            
        # Xoá rỗng kho Replica sau khi đã thăng cấp
        self.replica_store.clear()
        self.replica_content_store.clear()
        
        import logging
        if promoted_dht > 0 or promoted_content > 0:
            logging.getLogger("uvicorn.error").info(f"Node {getattr(self, 'node_id', '?')} PROMOTED {promoted_dht} index keys and {promoted_content} contents from Replica to Primary.")

    def _re_replicate(self, target_successor_id: int):
        """
        Re-replication: Đóng gói toàn bộ Primary data và gửi sang Successor mới để làm Backup.
        Gọi sau khi _promote_replicas xong, HOẶC khi stabilize() phát hiện đổi Successor.
        """
        my_id = getattr(self, "node_id", None)
        if target_successor_id is None or my_id is None or target_successor_id == my_id:
            return
            
        # 1. Re-replicate DHT Store
        for keyword, doc_ids in self.dht_store.items():
            self.transport.send(
                target_successor_id,
                Message("STORE_REPLICA", my_id, {"keyword": keyword, "doc_ids": list(doc_ids)}),
                timeout_ms=1000
            )
            
        # 2. Re-replicate Content Store
        for doc_id, content in self.content_store.items():
            self.transport.send(
                target_successor_id,
                Message("STORE_CONTENT_REPLICA", my_id, {"doc_id": doc_id, "content": content}),
                timeout_ms=1000
            )
        
    def _handle_get_content(self, message: Message) -> Response:
        """Lấy nội dung document từ DHT."""
        payload = message.payload
        doc_id = payload["doc_id"]
        
        content = self.content_store.get(doc_id, None)
        return Response(success=True, data={"doc_id": doc_id, "content": content})
        
    def _handle_store_content_replica(self, message: Message) -> Response:
        """Lưu bản sao nội dung document từ Predecessor."""
        payload = message.payload
        doc_id = payload["doc_id"]
        content = payload["content"]
        
        self.replica_content_store[doc_id] = content
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
                
        content_to_transfer: Dict[int, dict] = {}
        content_to_remove: List[int] = []
        
        if hasattr(self, 'content_store'):
            for doc_id, content in self.content_store.items():
                key_id = deterministic_hash(str(doc_id), self.m)
                should_transfer = False
                
                if old_predecessor_id is None or old_predecessor_id == self.node_id:
                    if not in_range(key_id, new_predecessor_id, self.node_id, inclusive_left=False, inclusive_right=True):
                        should_transfer = True
                else:
                    if in_range(key_id, old_predecessor_id, new_predecessor_id, inclusive_left=False, inclusive_right=True):
                        should_transfer = True
                        
                if should_transfer:
                    content_to_transfer[doc_id] = content
                    content_to_remove.append(doc_id)
        
        if not keys_to_transfer and not content_to_transfer:
            return
        
        # Gửi toàn bộ dữ liệu cho predecessor mới (bulk transfer)
        response = self.transport.send(
            new_predecessor_id,
            Message("TRANSFER_KEYS", self.node_id, {"keys": keys_to_transfer, "contents": content_to_transfer})
        )
        
        # Chỉ xóa dữ liệu nếu chuyển giao thành công
        if response.success:
            for keyword in keys_to_remove:
                del self.dht_store[keyword]
            for doc_id in content_to_remove:
                del self.content_store[doc_id]

    def _handle_transfer_keys(self, message: Message) -> Response:
        """Nhận bàn giao dữ liệu từ successor khi mình vừa join vào mạng."""
        payload = message.payload
        keys_data = payload.get("keys", {})
        contents_data = payload.get("contents", {})
        
        for keyword, doc_ids_list in keys_data.items():
            if keyword not in self.dht_store:
                self.dht_store[keyword] = set()
            self.dht_store[keyword].update(doc_ids_list)
            
        for doc_id_str, content in contents_data.items():
            doc_id = int(doc_id_str)
            self.content_store[doc_id] = content
        
        return Response(success=True)


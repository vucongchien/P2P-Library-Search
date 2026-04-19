import pytest
from src.chord.utils import in_range, deterministic_hash
from src.chord import ChordNode
from src.transport import LocalTransport
from src.models import Message, Response, ErrorCode

def test_in_range():
    """Kiểm tra logic Toán tử Vòng tròn DHT."""
    # Test m=8 (0 -> 255)
    # in range normal
    assert in_range(5, 1, 10) is True
    assert in_range(1, 1, 10, inclusive_left=True) is True
    assert in_range(10, 1, 10, inclusive_right=True) is True
    
    # in range vắt qua 0
    # Xét khoảng đóng (250, 10] -> Tương đương lớn hơn 250 tới 255, sập về 0 chạy tới 10 (lúc này m chưa giới hạn nhưng Logic dựa trên start > end)
    assert in_range(255, 250, 10) is True
    assert in_range(5, 250, 10) is True
    assert in_range(12, 250, 10) is False

def test_deterministic_hash():
    """Kiểm tra Hash luôn ổn định trên nhiều lần băm của cùng 1 chuỗi."""
    h1 = deterministic_hash("hello_world", 8)
    h2 = deterministic_hash("hello_world", 8)
    h3 = deterministic_hash("hello_world", 10) # Test khác space
    assert h1 == h2
    assert isinstance(h1, int)
    assert 0 <= h1 < 256
    assert 0 <= h3 < 1024


class TestChordNode:
    def setup_method(self):
        """Khởi tạo một transport và tạo ra cluster Node ảo cho test case."""
        self.transport = LocalTransport()
        self.node_10 = ChordNode(node_id=10, transport=self.transport)
        self.node_20 = ChordNode(node_id=20, transport=self.transport)
        self.node_50 = ChordNode(node_id=50, transport=self.transport)
        
        # Đưa vào mạng Local
        self.transport.register(10, self.node_10)
        self.transport.register(20, self.node_20)
        self.transport.register(50, self.node_50)

    # ==========================
    # TEST TASK 3: DISPATCHER
    # ==========================
    def test_handle_valid_and_invalid_message(self):
        """Node nhận message Lạ sẽ trả lỗi Unknown."""
        res_bad = self.node_10.handle_message(Message(type="SUPER_BAD", sender_id=9))
        assert res_bad.success is False
        assert res_bad.error == ErrorCode.UNKNOWN_TYPE
        
        res_get_pred = self.node_10.handle_message(Message(type="GET_PREDECESSOR", sender_id=9))
        assert res_get_pred.success is True
        assert res_get_pred.data["predecessor"] is None

    # ==========================
    # TEST TASK 4: ROUTING
    # ==========================
    def test_routing_find_successor_local(self):
        """Tìm key do mảng Ring của Node trực tiếp giữ."""
        self.node_10.successor_id = 20
        # Key 15 nằm giữa 10 và 20 -> successor của nó là 20. Bản thân Node 10 tự biết luôn (hưởng return Local).
        target = self.node_10.find_successor(15)
        assert target == 20
        
    def test_routing_find_successor_remote(self):
        """Dùng O(log N) bằng qua Transport."""
        # Giả lập: Ring có 10 -> 20 -> 50
        self.node_10.successor_id = 20
        self.node_10.finger_table[0] = 50 # Móc giả định nhảy cóc Finger
        
        self.node_50.successor_id = 60
        
        # Ai là người giữ Key 55? => Thằng 60.
        # Từ 10 nhảy qua 50 theo table. Từ 50 dò thấy nó quản đến 60.
        target = self.node_10.find_successor(55)
        # Node 10 -> gọi send tới 50 -> 50 trả về Successor là 60
        assert target == 60
        
    def test_routing_loop_ttl_prevention(self):
        """Nếu cấu hình sai lệch Topology tạo thành vô cực mượn nhau."""
        # Buộc Node 10 luôn đẩy sang 20, 20 luôn đẩy sang 10
        self.node_10.closest_preceding_node = lambda k: 20
        self.node_20.closest_preceding_node = lambda k: 10
        
        # Vô hiệu hóa việc tự thoả mãn locally
        import src.chord.routing_mixin as rf
        original_in_range = rf.in_range
        rf.in_range = lambda val, start, end, **kwargs: False
        
        try:
            with pytest.raises(RuntimeError) as exc_info:
                 self.node_10.find_successor(99) # Truy tìm key
                 
            assert "Cannot route" in str(exc_info.value)
        finally:
            rf.in_range = original_in_range

    # ==========================
    # TEST TASK 5: DHT STORAGE
    # ==========================
    def test_storage_put_and_get(self):
        """Test API Công Khai Put/Get ghi nhận vào DHT Store."""
        # Setup: Chúng ta thao túng tìm node luôn rớt vào node_20 bằng việc setup Finger
        self.node_10.successor_id = 20
        self.node_20.successor_id = 50 # Để Node 20 có chỗ Replicate
        
        # Test Put 2 lần 1 keyword (Mô phỏng 2 Node đều Push data -> gộp lại)
        res1 = self.node_10.put("database", {1, 2, 3})
        res2 = self.node_10.put("database", {3, 4, 5})
        assert res1 is True
        assert res2 is True
        
        # Thẩm định Data thực chất nằm dưới hầm của Node 20
        assert self.node_20.dht_store["database"] == {1, 2, 3, 4, 5}
        assert "database" not in self.node_10.dht_store # Chắc chắn Node 10 không giữ rác
        
        # Thẩm định Replica đã tự động được đẩy từ Node 20 sang Node 50
        assert self.node_50.replica_store["database"] == {1, 2, 3, 4, 5}
        
        # Test Get thông qua API Node 10, Node 10 call mạng sang 20
        res_docs = self.node_10.get("database")
        assert res_docs.success is True
        assert set(res_docs.data.get("doc_ids", [])) == {1, 2, 3, 4, 5}
        
    def test_storage_get_empty(self):
        self.node_10.successor_id = 20
        # Lấy từ chưa hề có 
        res_docs = self.node_10.get("not_exist")
        assert res_docs.success is True
        assert set(res_docs.data.get("doc_ids", [])) == set()

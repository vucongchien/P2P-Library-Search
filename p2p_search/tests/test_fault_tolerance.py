import pytest
import time
from src.chord.utils import deterministic_hash
from src.chord import ChordNode
from src.transport import LocalTransport
from src.models import Message, Response, ErrorCode

class TestFaultTolerance:
    def setup_method(self):
        """Khởi tạo một cluster ảo gồm 3 Node: 60, 110, 160."""
        self.transport = LocalTransport()
        self.node_60 = ChordNode(node_id=60, transport=self.transport)
        self.node_110 = ChordNode(node_id=110, transport=self.transport)
        self.node_160 = ChordNode(node_id=160, transport=self.transport)
        
        # Đăng ký vào transport mạng cục bộ
        self.transport.register(60, self.node_60)
        self.transport.register(110, self.node_110)
        self.transport.register(160, self.node_160)
        
        # Thiết lập cấu trúc Ring: 60 -> 110 -> 160 -> 60
        self.node_60.successor_id = 110
        self.node_60.predecessor_id = 160
        
        self.node_110.successor_id = 160
        self.node_110.predecessor_id = 60
        
        self.node_160.successor_id = 60
        self.node_160.predecessor_id = 110

    def test_bulk_re_replicate_and_overwrite(self):
        """Kiểm tra cơ chế Bulk Re-replication và ghi đè hoàn toàn Replica Store."""
        # 1. Đặt dữ liệu primary vào Node 110
        self.node_110.dht_store["python"] = {1, 2}
        self.node_110.dht_store["chord"] = {3}
        self.node_110.content_store[1] = {"title": "Doc 1"}
        
        # 2. Gọi re-replicate từ 110 sang successor (160)
        self.node_110._re_replicate(160)
        
        # 3. Kiểm tra xem Node 160 đã nhận đúng bản replica hay chưa
        assert self.node_160.replica_store["python"] == {1, 2}
        assert self.node_160.replica_store["chord"] == {3}
        assert self.node_160.replica_content_store[1] == {"title": "Doc 1"}
        
        # 4. Thay đổi Primary dữ liệu ở Node 110 (xoá chord, sửa python)
        self.node_110.dht_store.pop("chord")
        self.node_110.dht_store["python"] = {1, 2, 4}
        
        # 5. Gọi re-replicate lần nữa
        self.node_110._re_replicate(160)
        
        # 6. Kiểm tra xem 160 có tự động ghi đè và đồng bộ hoàn hảo không (không được giữ lại key 'chord' cũ)
        assert self.node_160.replica_store["python"] == {1, 2, 4}
        assert "chord" not in self.node_160.replica_store  # Phải bị xoá đi do cơ chế overwrite!

    def test_robust_ping_tolerates_transient_failures(self):
        """Kiểm tra liveness check của check_predecessor chống chịu được lỗi ping tạm thời."""
        # Giả lập: Ping thất bại 2 lần đầu, thành công ở lần thứ 3
        failures = 0
        original_send = self.transport.send
        
        def mock_send(to_node_id, message, timeout_ms=5000):
            nonlocal failures
            if message.type == "PING" and to_node_id == 60:
                if failures < 2:
                    failures += 1
                    return Response(success=False, error=ErrorCode.TIMEOUT)
            return original_send(to_node_id, message, timeout_ms)
            
        self.node_110.transport.send = mock_send
        
        # Gọi kiểm tra predecessor. Lỗi ping 2 lần tạm thời không được làm predecessor biến thành None!
        self.node_110.check_predecessor()
        assert self.node_110.predecessor_id == 60
        assert failures == 2

    def test_robust_ping_detects_permanent_failure(self):
        """Kiểm tra liveness check nhận diện đúng predecessor chết thật sau 3 lần ping fail."""
        # Giả lập: Cả 3 lần ping đều lỗi
        original_send = self.transport.send
        failures = 0
        
        def mock_send(to_node_id, message, timeout_ms=5000):
            nonlocal failures
            if message.type == "PING" and to_node_id == 60:
                failures += 1
                return Response(success=False, error=ErrorCode.TIMEOUT)
            return original_send(to_node_id, message, timeout_ms)
            
        self.node_110.transport.send = mock_send
        
        # Giả lập Node 110 đang giữ bản sao của Node 60
        self.node_110.replica_store["p2p"] = {10}
        self.node_110.replica_content_store[10] = {"title": "P2P Research"}
        
        # Chạy check_predecessor, phải phát hiện chết thật sau 3 lần ping
        self.node_110.check_predecessor()
        assert self.node_110.predecessor_id is None
        assert failures == 3
        
        # Xác nhận đã tự động promote dữ liệu của 60 lên Primary
        assert self.node_110.dht_store["p2p"] == {10}
        assert self.node_110.content_store[10] == {"title": "P2P Research"}
        
        # Xác nhận replica store của Node 110 đã bị cleared sau promotion
        assert len(self.node_110.replica_store) == 0

    def test_self_healing_maintain_data(self):
        """Kiểm tra cơ chế tự chữa lành (Self-Healing) khi phát hiện dữ liệu đi lạc."""
        # Đăng ký Finger của Node 110 và Node 160 để định tuyến đúng
        self.node_60.finger_table[0] = 110
        self.node_110.finger_table[0] = 160
        self.node_160.finger_table[0] = 60
        
        # 1. Cố ý ghi đè dữ liệu bị sai vào Node 110
        # Một keyword băm ra key_id = 150. Khoảng quản lý của 110 là (60, 110]. 
        # Vậy key_id = 150 phải thuộc về Node 160 quản lý (khoảng 110, 160]).
        # Nhưng ta lưu trực tiếp vào Node 110.
        keyword = "misplaced_word"
        h = deterministic_hash(keyword, 8)  # Chạy thử xem hash bằng bao nhiêu
        
        # Thiết lập thủ công để test
        self.node_110.dht_store[keyword] = {99}
        
        # Chạy maintain_data trên Node 110
        self.node_110.maintain_data()
        
        # Nếu hash của "misplaced_word" không thuộc quản lý của 110, nó phải bị chuyển sang node đúng (Node 160 hoặc Node 60)
        # Hãy xem từ khoá này đã biến mất khỏi Node 110 và chui vào đúng node chịu trách nhiệm chưa
        assert keyword not in self.node_110.dht_store
        
        # Tìm xem node nào đang chứa nó
        found = False
        for node in [self.node_60, self.node_110, self.node_160]:
            if keyword in node.dht_store:
                found = True
                assert node.dht_store[keyword] == {99}
                break
        assert found is True, "Từ khoá đi lạc phải được chuyển về đúng node chịu trách nhiệm"

    def test_successor_death_trigger_re_replication(self):
        """
        Kiểm tra kịch bản Successor chết trên vòng ring thực tế:
        10 -> 60 -> 110 -> 160 -> 10.
        Khi 60 chết, Node 110 thăng cấp thành công dữ liệu của 60,
        và sau khi Ring ổn định, Node 110 phải nhận được replica của Node 10
        thông qua cơ chế Smart Notify-Driven Re-replication.
        """
        # 1. Khởi tạo thêm Node 10 và đăng ký
        self.node_10 = ChordNode(node_id=10, transport=self.transport)
        self.transport.register(10, self.node_10)
        
        # 2. Thiết lập vòng ring: 10 -> 60 -> 110 -> 160 -> 10
        self.node_10.successor_id = 60
        self.node_10.predecessor_id = 160
        self.node_10.successor_list = [60, 110, 160]
        
        self.node_60.predecessor_id = 10
        self.node_60.successor_id = 110
        self.node_60.successor_list = [110, 160, 10]
        
        self.node_110.predecessor_id = 60
        self.node_110.successor_id = 160
        self.node_110.successor_list = [160, 10, 60]
        
        # 3. Ghi dữ liệu ban đầu
        # Node 10 chứa key "node_10_key", replica ở Node 60
        self.node_10.dht_store["node_10_key"] = {10}
        self.node_60.replica_store["node_10_key"] = {10}
        
        # Node 60 chứa key "node_60_key", replica ở Node 110
        self.node_60.dht_store["node_60_key"] = {60}
        self.node_110.replica_store["node_60_key"] = {60}
        
        # 4. Giả lập Node 60 bị sập nguồn (chết hẳn)
        # Bằng cách mock send sang Node 60 trả về timeout lỗi
        original_send = self.transport.send
        def mock_send(to_node_id, message, timeout_ms=5000):
            if to_node_id == 60:
                return Response(success=False, error=ErrorCode.TIMEOUT)
            return original_send(to_node_id, message, timeout_ms)
        self.transport.send = mock_send
        self.node_10.transport.send = mock_send
        self.node_110.transport.send = mock_send
        
        # 5. Bước 1: Node 10 chạy stabilize() phát hiện 60 chết, cập nhật successor sang 110, gửi NOTIFY
        self.node_10.stabilize()
        assert self.node_10.successor_id == 110
        
        # Ở thời điểm này, Node 110 chưa chạy check_predecessor nên vẫn giữ predecessor = 60
        # NOTIFY từ Node 10 sẽ bị từ chối cập nhật predecessor (để bảo vệ replica của 60 trên 110).
        # Đảm bảo Node 110 chưa nhận replica của Node 10, và replica của 60 vẫn an toàn.
        assert self.node_110.predecessor_id == 60
        assert "node_10_key" not in self.node_110.replica_store
        assert self.node_110.replica_store["node_60_key"] == {60}
        
        # 6. Bước 2: Node 110 chạy check_predecessor() phát hiện 60 chết thật,
        # thăng cấp (promote) replica của 60 lên primary, rồi gán predecessor = None
        self.node_110.check_predecessor()
        assert self.node_110.predecessor_id is None
        assert self.node_110.dht_store["node_60_key"] == {60}
        assert len(self.node_110.replica_store) == 0  # Replica store được clear sau khi thăng cấp
        
        # 7. Bước 3: Ở chu kỳ stabilize() tiếp theo của Node 10, Node 10 lại gửi NOTIFY
        # Lần này Node 110 có predecessor = None nên sẽ chấp nhận Node 10 làm predecessor mới
        # và trả về updated: True -> Node 10 lập tức re-replicate dữ liệu chính của nó sang Node 110.
        self.node_10.stabilize()
        
        # Kiểm tra kết quả cuối cùng:
        assert self.node_110.predecessor_id == 10
        # Node 110 PHẢI nhận được replica dữ liệu của Node 10!
        assert self.node_110.replica_store["node_10_key"] == {10}


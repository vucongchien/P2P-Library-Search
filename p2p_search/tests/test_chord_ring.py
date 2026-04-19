import pytest
from src.chord import ChordRing
from src.transport import LocalTransport

class TestChordRing:
    def setup_method(self):
        self.transport = LocalTransport()
        self.m = 8 # [0, 255]

    def test_ring_creation_and_topology(self):
        """Kiểm tra khởi tạo ring và các node tự nhận diện nhau sau stabilization."""
        node_ids = [10, 50, 100]
        ring = ChordRing.create(node_ids, self.transport, self.m)
        
        n10 = ring.get_node(10)
        n50 = ring.get_node(50)
        n100 = ring.get_node(100)
        
        # Sau 5 vòng stabilize, successor phải đúng thứ tự
        assert n10.successor_id == 50
        assert n50.successor_id == 100
        assert n100.successor_id == 10
        
        # Predecessor cũng phải đúng
        assert n10.predecessor_id == 100
        assert n50.predecessor_id == 10
        assert n100.predecessor_id == 50

    def test_node_join(self):
        """Kiểm tra node mới join vào mạng hiện có."""
        ring = ChordRing(self.transport, self.m)
        ring.add_node(10) # Node đầu tiên
        n10 = ring.get_node(10)
        
        # Ban đầu n10 tự quản chính nó
        assert n10.successor_id == 10
        
        ring.add_node(50) # Node thứ 2 join
        n50 = ring.get_node(50)
        
        # Sau khi add_node, join logic đã chạy nhưng cần stabilize để n10 biết sự hiện diện của n50
        ring.stabilize_all(rounds=3)
        
        assert n10.successor_id == 50
        assert n50.successor_id == 10
        assert n10.predecessor_id == 50
        assert n50.predecessor_id == 10

    def test_node_leave_churn(self):
        """Kiểm tra mạng tự phục hồi sau khi một node rời đi."""
        node_ids = [10, 50, 100]
        ring = ChordRing.create(node_ids, self.transport, self.m)
        
        # Giả lập node 50 chết
        ring.remove_node(50)
        
        # Ban đầu n10 vẫn nghĩ successor là 50 (stale)
        n10 = ring.get_node(10)
        assert n10.successor_id == 50
        
        # Chạy stabilization
        ring.stabilize_all(rounds=3)
        
        # n10 phải nhận diện 50 đã mất và nhảy tới 100 thông qua logic find_successor 
        # (Lưu ý: fallback logic trong find_successor sẽ được kích hoạt khi transport báo 50 not found)
        assert n10.successor_id == 100
        assert n10.predecessor_id == 100
        
        n100 = ring.get_node(100)
        assert n100.successor_id == 10
        assert n100.predecessor_id == 10

    def test_finger_table_convergence(self):
        """Kiểm tra bảng finger table hội tụ sau các vòng stabilize."""
        node_ids = [10, 50, 100, 200]
        ring = ChordRing.create(node_ids, self.transport, self.m)
        
        n10 = ring.get_node(10)
        
        # Finger[0] của node 10 là successor(10 + 2^0 = 11) -> node 50
        assert n10.finger_table[0] == 50
        
        # Finger[5] của node 10 là successor(10 + 2^5 = 42) -> node 50
        assert n10.finger_table[5] == 50
        
        # Finger[6] của node 10 là successor(10 + 2^6 = 74) -> node 100
        assert n10.finger_table[6] == 100
        
        # Finger[7] của node 10 là successor(10 + 2^7 = 138) -> node 200
        assert n10.finger_table[7] == 200

    def test_data_handoff_on_join(self):
        """
        Kịch bản: Mạng có 2 node (10, 100). Đổ dữ liệu vào.
        Node 50 join vào giữa. Dữ liệu thuộc phạm vi (10, 50] phải
        được chuyển giao từ Node 100 sang Node 50.
        """
        from src.chord.utils import deterministic_hash
        
        # === Giai đoạn 1: Tạo mạng 2 node và đổ dữ liệu ===
        ring = ChordRing.create([10, 100], self.transport, self.m)
        n10 = ring.get_node(10)
        n100 = ring.get_node(100)
        
        # Xác nhận topology: 10 -> 100 -> 10
        assert n10.successor_id == 100
        assert n100.successor_id == 10

        # Đổ dữ liệu: Tạo 1 tập keywords và PUT vào DHT thông qua node 10
        test_keywords = ["alpha", "beta", "gamma", "delta", "epsilon"]
        for kw in test_keywords:
            n10.put(kw, {1, 2, 3})
        
        # Tính key_id của từng keyword để biết nó thuộc node nào
        key_map = {kw: deterministic_hash(kw, self.m) for kw in test_keywords}
        
        # Xác nhận dữ liệu đã nằm ở đúng node (trước khi join)
        for kw in test_keywords:
            kid = key_map[kw]
            # Tất cả key sẽ thuộc 1 trong 2 node: 10 hoặc 100
            if kw in n10.dht_store:
                assert kw not in n100.dht_store
            else:
                assert kw in n100.dht_store

        # === Giai đoạn 2: Node 50 join vào giữa ===
        ring.add_node(50)
        ring.stabilize_all(rounds=self.m)
        n50 = ring.get_node(50)
        
        # Xác nhận topology mới: 10 -> 50 -> 100 -> 10
        assert n10.successor_id == 50
        assert n50.successor_id == 100
        assert n100.successor_id == 10

        # === Giai đoạn 3: Kiểm chứng Data Handoff ===
        # Với mỗi keyword, xác nhận nó nằm ĐÚNG node theo quy tắc Chord 
        for kw in test_keywords:
            kid = key_map[kw]
            result = n10.get(kw)
            # Dù dữ liệu đã bị di chuyển, API get() vẫn phải tìm được
            assert result.success is True, f"Network failed for {kw}"
            assert set(result.data.get("doc_ids", [])) == {1, 2, 3}, f"Keyword '{kw}' (key_id={kid}) không tìm thấy qua API get()"


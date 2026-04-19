import pytest
import json
from src.chord.ring import ChordRing
from src.transport import LocalTransport
from src.chord.utils import deterministic_hash

class TestPublishP2P:
    """Kiểm thử tính năng tự động Index và Publish của Node theo chuẩn P2P thực tế."""
    
    def test_node_local_publish_and_merge(self):
        # 1. Khai báo Nhạc Trưởng Mạng giả lập (Transport + Ring)
        transport = LocalTransport()
        ring = ChordRing(transport=transport, m=8)
        for i in range(5):
            ring.add_node(i * 50) # Tự tạo ID cách xa nhau
        ring.stabilize_all(rounds=5) # Đợi mạng ổn định
        
        # 2. Rút ngẫu nhiên ra 2 Node từ Mạng
        nodes = list(ring.nodes.values())
        peer_0 = nodes[0]
        peer_1 = nodes[1]
        peer_2 = nodes[2]
        
        # 3. Môi trường giả lập: Bơm dữ liệu (Giả lập Node vừa đọc File xong)
        peer_0.load_local_index({
            "system": [1, 2],
            "database": [5]
        })
        
        peer_1.load_local_index({
            "system": [3, 4], # Trùng chữ 'system' với Peer 0
            "network": [10]
        })
        
        # 4. Hành động độc lập: Từng Node tự nguyện đem dữ liệu của mình Publish lên Mạng
        peer_0.publish()
        peer_1.publish()
        
        # 5. Quan sát (Ground Truth): Hãy lấy 1 node KHÁC biệt (VD peer_2) và truy vấn thử
        # Hàm get() của ChordNode sẽ tự định tuyến tới Node thực sự giữ khóa "system"
        res_system = peer_2.get("system")
        res_database = peer_2.get("database")
        res_network = peer_2.get("network")
        
        system_result = res_system.data.get("doc_ids", [])
        database_result = res_database.data.get("doc_ids", [])
        network_result = res_network.data.get("doc_ids", [])
        
        # 6. Xác Nhận:
        # Nhờ tính chất `storage_mixin.py` dùng UNION kết hợp với Hash chuẩn, Data Merge phải thành công!
        assert res_system.success is True
        assert set(system_result) == {1, 2, 3, 4}, f"Expected {{1, 2, 3, 4}}, got {system_result}"
        assert set(database_result) == {5}, f"Expected {{5}}, got {database_result}"
        assert set(network_result) == {10}, f"Expected {{10}}, got {network_result}"
        
        # 7. In ra Console báo cáo để User nhìn thấy cụ thể dữ liệu hoạt động thế nào
        print("\n\n=== KET QUA DINH TUYEN MANG DHT (PUBLISH THANH CONG) ===")
        print(f"Tu khoa 'system' duoc tong hop: {system_result}")
        print(f"Tu khoa 'database' duoc luu la: {database_result}")
        print(f"Tu khoa 'network' duoc luu la: {network_result}")
        
        # Ta có thể bóc trần bộ nhớ của Node đang chịu trách nhiệm cho "system"
        key_id = deterministic_hash("system", 8)
        target_id = peer_2.find_successor(key_id)
        target_node = ring.get_node(target_id)
        print(f"-> Tu khoa 'system' (Hash: {key_id}) dang duoc cat giu TAP TRUNG tai Node: {target_node.node_id}")
        print(f"Du lieu DHT Store cua Node {target_node.node_id}: {target_node.dht_store}")
        
    def test_publish_empty_node(self):
        """Xác nhận Node không có Local Index gọi Publish thì bỏ qua an toàn."""
        transport = LocalTransport()
        ring = ChordRing(transport=transport, m=8)
        ring.add_node(10)
        ring.add_node(20)
        peer_0 = list(ring.nodes.values())[0]
        
        # Chạy publish rỗng không crash
        peer_0.publish()
        
        # DHT vẫn trống
        assert len(peer_0.dht_store) == 0

from src.models import Message, Response, ErrorCode
from .utils import in_range
from typing import List, Optional

class RoutingMixin:
    """
    Mixin đảm nhiệm logic Routing O(log N) bằng thuật toán Chord.
    """
    # Gợi ý kiểu cho Editor/IDE hiểu cấu trúc (được khai báo thực tế tại lớp Node)
    node_id: int
    m: int
    successor_id: int
    predecessor_id: Optional[int]
    finger_table: List[int]
    transport: 'Transport' # type: ignore

    def closest_preceding_node(self, key_id: int) -> int:
        """Dò ngược Finger Table để tìm Node gần key_id nhất ở cung bên trái."""
        # Nếu key chính là ta, không cần tìm kiếm trong finger để tránh edge cases rắc rối
        if key_id == self.node_id:
            return self.node_id

        for i in range(self.m - 1, -1, -1):
            finger_id = self.finger_table[i]
            if finger_id is not None and in_range(finger_id, self.node_id, key_id):
                return finger_id
        return self.node_id

    def find_successor(self, key_id: int) -> int:
        """Api công khai để tìm target peer quản lý key_id."""
        if in_range(key_id, self.node_id, self.successor_id, inclusive_right=True):
            return self.successor_id

        n_prime = self.closest_preceding_node(key_id)
        if n_prime == self.node_id:
            return self.successor_id

        # Mượn Transport để đi tiếp
        response = self.transport.send(
            to_node_id=n_prime,
            message=Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
        )

        if not response.success:
            return self._handle_routing_failure(key_id, n_prime)

        return response.data["successor"]

    def _handle_find_successor(self, message: Message) -> Response:
        """Handler nội bộ khi có Node khác gọi qua mạng nhờ mình tìm."""
        payload = message.payload
        ttl = message.ttl
        key_id = payload["key"]

        if ttl <= 0:
            return Response(success=False, error=ErrorCode.ROUTING_LOOP)
        
        if in_range(key_id, self.node_id, self.successor_id, inclusive_right=True):
             return Response(success=True, data={"successor": self.successor_id})

        n_prime = self.closest_preceding_node(key_id)
        if n_prime == self.node_id:
             return Response(success=True, data={"successor": self.successor_id})

        # Vẫn chưa tới, Chuyển tiếp (forward) đi nơi khác qua mạng, giảm TTL
        response = self.transport.send(
             n_prime,
             Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=ttl - 1)
        )
        return response

    def _handle_routing_failure(self, key_id: int, dead_node_id: int) -> int:
        """Khắc phục rủi ro đứt mạng bằng cách thử nhánh mạng khác."""
        # 1. Thử các finger khác trong bảng (ưu tiên đúng range)
        for i in range(self.m - 1, -1, -1):
            finger_id = self.finger_table[i]
            if finger_id == dead_node_id or finger_id is None or finger_id == self.node_id:
                continue
                
            # Chỉ gửi nếu finger này nằm trong range hữu ích hoặc nếu ta đang bế tắc
            if in_range(finger_id, self.node_id, key_id):
                response = self.transport.send(
                    finger_id,
                    Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
                )
                if response.success:
                    return response.data["successor"]
        
        # 2. Bước dự phòng: Thử BẤT KỲ finger nào còn sống để thoát khỏi bế tắc
        for finger_id in reversed([f for f in self.finger_table if f not in [None, self.node_id, dead_node_id]]):
            response = self.transport.send(
                finger_id,
                Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
            )
            if response.success:
                return response.data["successor"]

        # 3. Phá sản định tuyến
        raise RuntimeError(f"Cannot route to key {key_id} from Node {self.node_id}: all paths dead")

    def join(self, known_node_id: Optional[int]):
        """Tham gia vào mạng Chord thông qua một node đã biết."""
        if known_node_id is not None:
            self.predecessor_id = None
            response = self.transport.send(
                known_node_id,
                Message("FIND_SUCCESSOR", self.node_id, {"key": self.node_id})
            )
            if response.success:
                self.successor_id = response.data["successor"]
                self.finger_table[0] = self.successor_id # Finger 0 luôn là successor
            else:
                raise RuntimeError(f"Could not join network via node {known_node_id}: {response.error}")
        else:
            # Đây là node đầu tiên trong mạng
            self.successor_id = self.node_id
            self.finger_table[0] = self.node_id
            self.predecessor_id = None

    def stabilize(self):
        """Định kỳ kiểm tra successor và thông báo cho nó về sự hiện diện của mình."""
        # Hỏi successor về predecessor của nó
        response = self.transport.send(
            self.successor_id,
            Message("GET_PREDECESSOR", self.node_id)
        )
        
        if response.success:
            x = response.data.get("predecessor")
            # x ∈ (self, successor)
            # Điều kiện bootstrap: Nếu ta đang là node duy nhất (successor_id == self.node_id),
            # và nhận được một x hợp lệ, thì x chính là successor mới.
            is_better_successor = False
            if x is not None and x != self.node_id:
                if self.successor_id == self.node_id:
                    is_better_successor = True
                elif in_range(x, self.node_id, self.successor_id, inclusive_left=False, inclusive_right=False):
                    is_better_successor = True
            
            if is_better_successor:
                self.successor_id = x
                self.finger_table[0] = x # Đồng bộ finger table
        else:
            # Successor đã chết! Phải tìm successor mới từ finger table
            for i in range(1, self.m):
                finger_id = self.finger_table[i]
                if finger_id is not None and finger_id != self.node_id:
                    # Kiểm tra xem node này còn sống không
                    ping_res = self.transport.send(finger_id, Message("PING", self.node_id))
                    if ping_res.success:
                        self.successor_id = finger_id
                        self.finger_table[0] = finger_id
                        break
        
        # Thông báo cho successor về mình (nếu còn sống)
        self.transport.send(
            self.successor_id,
            Message("NOTIFY", self.node_id, {"node_id": self.node_id})
        )

    def fix_fingers(self):
        """Định kỳ cập nhật một mục trong finger table."""
        if not hasattr(self, 'next_finger_to_fix'):
            self.next_finger_to_fix = 0
            
        # Tính toán key start của finger thứ i: (n + 2^i) mod 2^m
        target_key = (self.node_id + (2 ** self.next_finger_to_fix)) % (2 ** self.m)
        self.finger_table[self.next_finger_to_fix] = self.find_successor(target_key)
        
        # Tăng index cho lần gọi tiếp theo
        self.next_finger_to_fix += 1
        if self.next_finger_to_fix >= self.m:
            self.next_finger_to_fix = 0

    def check_predecessor(self):
        """Kiểm tra xem predecessor còn sống không."""
        if self.predecessor_id is not None:
            response = self.transport.send(
                self.predecessor_id,
                Message("PING", self.node_id)
            )
            if not response.success:
                self.predecessor_id = None

    def _handle_get_predecessor(self, message: Message) -> Response:
        return Response(success=True, data={"predecessor": self.predecessor_id})

    def _handle_notify(self, message: Message) -> Response:
        candidate_node_id = message.payload["node_id"]
        # Điều kiện cập nhật predecessor:
        # 1. Chưa có predecessor
        # 2. Predecessor hiện tại là chính mình (đang cô đơn)
        # 3. candidate mới nằm trong khoảng (predecessor_id, node_id)
        should_update = False
        if candidate_node_id != self.node_id:
            if self.predecessor_id is None or self.predecessor_id == self.node_id:
                should_update = True
            elif in_range(candidate_node_id, self.predecessor_id, self.node_id, inclusive_left=False, inclusive_right=False):
                should_update = True
        
        if should_update:
            old_predecessor_id = self.predecessor_id
            self.predecessor_id = candidate_node_id
            
            # Data Handoff: Chuyển giao key thuộc phạm vi predecessor mới
            self._transfer_keys_to_predecessor(candidate_node_id, old_predecessor_id)
            
        return Response(success=True)

    def _handle_ping(self, message: Message) -> Response:
        return Response(success=True)

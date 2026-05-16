from src.models import Message, Response, ErrorCode, RoutingHop, RoutingTrace
from .utils import in_range
from typing import List, Optional

class RoutingMixin:
    """
    Mixin đảm nhiệm logic Routing O(log N) bằng thuật toán Chord.
    
    Trace System: Mỗi node khi tham gia routing tự ghi lại quyết định của mình
    vào response.data["path"]. Path tích lũy qua từng hop → source of truth.
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

    # ----------------------------------------------------------
    # find_successor — backward compat (trả int)
    # ----------------------------------------------------------

    def find_successor(self, key_id: int) -> int:
        """Api công khai để tìm target peer quản lý key_id. Trả về node_id."""
        trace = self.find_successor_traced(key_id)
        return trace.target_id

    # ----------------------------------------------------------
    # find_successor_traced — trả RoutingTrace đầy đủ
    # ----------------------------------------------------------

    def find_successor_traced(self, key_id: int) -> RoutingTrace:
        """
        Tìm successor chịu trách nhiệm key_id + trả routing trace đầy đủ.
        
        Trace ghi chính xác:
        - ORIGIN: node khởi tạo lookup
        - SELF: key thuộc chính node này (successor = self)
        - RESOLVED: key thuộc khoảng (self, successor] → trả successor
        - FORWARD: chuyển tiếp qua transport tới node khác
        """
        # Case 1: Successor chính là mình (single node ring)
        if self.successor_id == self.node_id:
            hop = RoutingHop(
                node_id=self.node_id,
                action="SELF",
                target_key=key_id,
                next_node=self.node_id,
                reason=f"single node ring, self is successor"
            )
            return RoutingTrace(key=key_id, target_id=self.node_id, path=[hop], success=True)

        # Case 2: Key nằm trong (self, successor] → successor là đích
        if in_range(key_id, self.node_id, self.successor_id, inclusive_right=True):
            hop = RoutingHop(
                node_id=self.node_id,
                action="RESOLVED",
                target_key=key_id,
                next_node=self.successor_id,
                reason=f"key {key_id} ∈ ({self.node_id}, {self.successor_id}]"
            )
            return RoutingTrace(key=key_id, target_id=self.successor_id, path=[hop], success=True)

        # Case 3: Cần forward qua mạng
        n_prime = self.closest_preceding_node(key_id)
        if n_prime == self.node_id:
            # Không tìm được finger tốt hơn → successor là best bet
            hop = RoutingHop(
                node_id=self.node_id,
                action="RESOLVED",
                target_key=key_id,
                next_node=self.successor_id,
                reason=f"no closer finger, fallback to successor N{self.successor_id}"
            )
            return RoutingTrace(key=key_id, target_id=self.successor_id, path=[hop], success=True)

        # Forward qua transport
        origin_hop = RoutingHop(
            node_id=self.node_id,
            action="FORWARD",
            target_key=key_id,
            next_node=n_prime,
            reason=f"closest_preceding_node -> N{n_prime}"
        )

        response = self.transport.send(
            to_node_id=n_prime,
            message=Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
        )

        if not response.success:
            # Routing failure → thử recovery
            recovery_result = self._handle_routing_failure_traced(key_id, n_prime)
            if recovery_result.success:
                return RoutingTrace(
                    key=key_id,
                    target_id=recovery_result.target_id,
                    path=[origin_hop] + recovery_result.path,
                    success=True
                )
            else:
                return RoutingTrace(
                    key=key_id, target_id=-1,
                    path=[origin_hop], success=False
                )

        target_id = response.data["successor"]
        downstream_path = [RoutingHop.from_dict(h) for h in response.data.get("path", [])]

        return RoutingTrace(
            key=key_id,
            target_id=target_id,
            path=[origin_hop] + downstream_path,
            success=True
        )

    # ----------------------------------------------------------
    # _handle_find_successor — tích lũy path trong response
    # ----------------------------------------------------------

    def _handle_find_successor(self, message: Message) -> Response:
        """Handler nội bộ khi có Node khác gọi qua mạng nhờ mình tìm."""
        payload = message.payload
        ttl = message.ttl
        key_id = payload["key"]

        if ttl <= 0:
            return Response(success=False, error=ErrorCode.ROUTING_LOOP)
        
        # Case 1: Key thuộc khoảng (self, successor]
        if in_range(key_id, self.node_id, self.successor_id, inclusive_right=True):
            hop = {
                "node": self.node_id,
                "action": "RESOLVED",
                "target_key": key_id,
                "next_node": self.successor_id,
                "reason": f"key {key_id} ∈ ({self.node_id}, {self.successor_id}]"
            }
            return Response(success=True, data={
                "successor": self.successor_id,
                "path": [hop]
            })

        # Case 2: Forward tiếp
        n_prime = self.closest_preceding_node(key_id)
        if n_prime == self.node_id:
            hop = {
                "node": self.node_id,
                "action": "RESOLVED",
                "target_key": key_id,
                "next_node": self.successor_id,
                "reason": f"no closer finger, fallback to successor N{self.successor_id}"
            }
            return Response(success=True, data={
                "successor": self.successor_id,
                "path": [hop]
            })

        # Forward qua mạng, giảm TTL
        my_hop = {
            "node": self.node_id,
            "action": "FORWARD",
            "target_key": key_id,
            "next_node": n_prime,
            "reason": f"closest_preceding_node -> N{n_prime}"
        }

        response = self.transport.send(
             n_prime,
             Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=ttl - 1)
        )

        if response.success:
            # Prepend hop của mình vào path downstream
            downstream_path = response.data.get("path", [])
            response.data["path"] = [my_hop] + downstream_path

        return response

    # ----------------------------------------------------------
    # Routing failure recovery
    # ----------------------------------------------------------

    def _handle_routing_failure(self, key_id: int, dead_node_id: int) -> int:
        """Khắc phục rủi ro đứt mạng bằng cách thử nhánh mạng khác. Backward compat."""
        result = self._handle_routing_failure_traced(key_id, dead_node_id)
        if result.success:
            return result.target_id
        raise RuntimeError(f"Cannot route to key {key_id} from Node {self.node_id}: all paths dead")

    def _handle_routing_failure_traced(self, key_id: int, dead_node_id: int) -> RoutingTrace:
        """Khắc phục routing failure với trace đầy đủ."""
        recovery_path = []

        # 1. Thử các finger khác trong bảng (ưu tiên đúng range)
        for i in range(self.m - 1, -1, -1):
            finger_id = self.finger_table[i]
            if finger_id == dead_node_id or finger_id is None or finger_id == self.node_id:
                continue
                
            if in_range(finger_id, self.node_id, key_id):
                response = self.transport.send(
                    finger_id,
                    Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
                )
                if response.success:
                    hop = RoutingHop(
                        node_id=self.node_id,
                        action="FORWARD",
                        target_key=key_id,
                        next_node=finger_id,
                        reason=f"recovery: finger[{i}] -> N{finger_id} (N{dead_node_id} dead)"
                    )
                    downstream = [RoutingHop.from_dict(h) for h in response.data.get("path", [])]
                    return RoutingTrace(
                        key=key_id,
                        target_id=response.data["successor"],
                        path=[hop] + downstream,
                        success=True
                    )
        
        # 2. Thử BẤT KỲ finger nào còn sống
        for finger_id in reversed([f for f in self.finger_table if f not in [None, self.node_id, dead_node_id]]):
            response = self.transport.send(
                finger_id,
                Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}, ttl=20)
            )
            if response.success:
                hop = RoutingHop(
                    node_id=self.node_id,
                    action="FORWARD",
                    target_key=key_id,
                    next_node=finger_id,
                    reason=f"recovery: any alive finger -> N{finger_id}"
                )
                downstream = [RoutingHop.from_dict(h) for h in response.data.get("path", [])]
                return RoutingTrace(
                    key=key_id,
                    target_id=response.data["successor"],
                    path=[hop] + downstream,
                    success=True
                )

        # 3. Phá sản
        return RoutingTrace(key=key_id, target_id=-1, path=[], success=False)

    # ----------------------------------------------------------
    # Join / Stabilize / Fix Fingers
    # ----------------------------------------------------------

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
                self.successor_list = [self.successor_id] # Khởi tạo danh sách với 1 successor
                self.finger_table[0] = self.successor_id # Finger 0 luôn là successor
            else:
                raise RuntimeError(f"Could not join network via node {known_node_id}: {response.error}")
        else:
            # Đây là node đầu tiên trong mạng
            self.successor_id = self.node_id
            self.successor_list = [self.node_id]
            self.finger_table[0] = self.node_id
            self.predecessor_id = None

    def stabilize(self):
        """Định kỳ kiểm tra successor và thông báo cho nó về sự hiện diện của mình."""
        r_size = 3 # Số lượng successor dự phòng
        
        # Hỏi successor về predecessor của nó
        response = self.transport.send(
            self.successor_id,
            Message("GET_PREDECESSOR", self.node_id)
        )
        
        if response.success:
            x = response.data.get("predecessor")
            # Cập nhật successor_list từ thông tin nhận được
            succ_list_from_node = response.data.get("successor_list", [])
            self.successor_list = [self.successor_id] + succ_list_from_node[:r_size-1]

            # x ∈ (self, successor)
            is_better_successor = False
            if x is not None and x != self.node_id:
                if self.successor_id == self.node_id:
                    is_better_successor = True
                elif in_range(x, self.node_id, self.successor_id, inclusive_left=False, inclusive_right=False):
                    is_better_successor = True
            
            if is_better_successor:
                self.successor_id = x
                self.finger_table[0] = x # Đồng bộ finger table
                # Nếu đổi successor, list sẽ được cập nhật ở vòng stabilize sau hoặc ngay tại đây
                self.successor_list = [self.successor_id] + self.successor_list[:r_size-1]
        else:
            # Successor đã chết! Phải tìm successor mới từ successor_list
            old_successor = self.successor_id
            found_new = False
            
            # Thử các node trong danh sách dự phòng
            for backup_id in self.successor_list:
                if backup_id == self.node_id or backup_id == old_successor:
                    continue
                ping_res = self.transport.send(backup_id, Message("PING", self.node_id))
                if ping_res.success:
                    self.successor_id = backup_id
                    self.finger_table[0] = backup_id
                    self.successor_list = [self.successor_id] # Reset list để cập nhật lại sau
                    found_new = True
                    break
            
            # Nếu list dự phòng cũng sập hết, fallback sang finger table như cũ
            if not found_new:
                for i in range(1, self.m):
                    finger_id = self.finger_table[i]
                    if finger_id is not None and finger_id != self.node_id and finger_id != old_successor:
                        ping_res = self.transport.send(finger_id, Message("PING", self.node_id))
                        if ping_res.success:
                            self.successor_id = finger_id
                            self.finger_table[0] = finger_id
                            self.successor_list = [self.successor_id]
                            found_new = True
                            break
            
            # Nếu tìm được Successor mới sau khi cái cũ chết, gửi Re-replicate
            if self.successor_id != old_successor and self.successor_id != self.node_id:
                if hasattr(self, '_re_replicate'):
                    self._re_replicate(self.successor_id)
        
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
        if getattr(self, "predecessor_id", None) is not None:
            response = self.transport.send(
                self.predecessor_id,
                Message("PING", self.node_id)
            )
            if not response.success:
                # Predecessor đã chết!
                self.predecessor_id = None
                
                # 1. Promote Replicas to Primary
                if hasattr(self, '_promote_replicas'):
                    self._promote_replicas()
                    
                # 2. Re-replicate the newly promoted primary to our successor
                if hasattr(self, '_re_replicate') and getattr(self, "successor_id", None) != getattr(self, "node_id", None):
                    self._re_replicate(self.successor_id)

    def _handle_get_predecessor(self, message: Message) -> Response:
        return Response(success=True, data={
            "predecessor": self.predecessor_id,
            "successor_list": getattr(self, "successor_list", [])
        })

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

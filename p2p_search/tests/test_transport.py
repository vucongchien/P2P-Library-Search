import pytest
from src.transport import LocalTransport
from src.models import Message, Response, ErrorCode

class MockNode:
    """Fake node (Node giả tạo) để phục vụ kiểm thử tương tác với Transport."""
    def __init__(self, node_id: int):
        self.node_id = node_id

    def handle_message(self, message: Message) -> Response:
        # Giả lập xử lý message: Trả về thành công nếu type là ECHO
        if message.type == "ECHO":
            return Response(success=True, data={"echo": message.payload})
        # Giả lập lỗi Exception tử vong giữa quá trình xử lý của Node
        if message.type == "BAD":
            raise ValueError("Something went terribly wrong!")
        # Mặc định báo lỗi type chưa hỗ trợ
        return Response(success=False, error=ErrorCode.UNKNOWN_TYPE)

class TestLocalTransport:
    def test_transport_registration(self):
        """Kiểm tra chức năng đăng ký và hủy đăng ký Node trên Transport."""
        # 1. Khởi tạo Transport và một Node ảo
        transport = LocalTransport()
        node = MockNode(10)
        
        # 2. Đăng ký Node vào mạng (Registry)
        transport.register(10, node)
        
        # 3. Assert (Xác nhận) Node 10 đã có trong Registry chưa
        assert 10 in transport.registry
        assert transport.registry[10] == node
        
        # 4. Hủy đăng ký Node 10
        transport.unregister(10)
        
        # 5. Xác nhận Node 10 đã bị xóa khỏi Registry hoàn toàn
        assert 10 not in transport.registry

    def test_send_message_success(self):
         """Kiểm tra chức năng gửi tin nhắn và nhận tín hiệu báo thành công."""
         # 1. Khởi tạo mạng và bật Node ID=10
         transport = LocalTransport()
         node = MockNode(10)
         transport.register(10, node)
         
         # 2. Tạo một message hợp lệ kiểu ECHO
         msg = Message(type="ECHO", sender_id=5, payload={"hello": "world"})
         
         # 3. Tiến hành gửi Message vào Transport để chuyển cho cục Node 10
         response = transport.send(10, msg)
         
         # 4. Xác nhận kết quả trả về là Thành Công rực rỡ và Payload chuẩn
         assert response.success is True
         assert response.data == {"echo": {"hello": "world"}}
         assert response.error is None
         
         # 5. Xác nhận Transport Log đã sao lưu Metric ghi nhận tin nhắn này đi qua
         assert len(transport.message_log) == 1
         assert transport.message_log[0] == msg

    def test_send_message_node_not_found(self):
        """Kiểm tra lỗi trả về khi Transport gửi nhầm tuyến cho Node không tồn tại."""
        # 1. Khởi tạo Transport (không đăng ký node nào cả)
        transport = LocalTransport()
        
        # 2. Tạo message PING
        msg = Message(type="PING", sender_id=5)
        
        # 3. Góp nhặt gửi message tới Node 999 (Node vô danh)
        response = transport.send(999, msg)
        
        # 4. Xác minh Transport đã chặn kịp bắt ra lỗi NODE_NOT_FOUND (không raise tung toé Exception)
        assert response.success is False
        assert response.error == ErrorCode.NODE_NOT_FOUND
        
        # 5. Metric ghi lưu vết thử gửi này
        assert len(transport.message_log) == 1

    def test_send_message_node_exception_handling(self):
        """Kiểm tra Transport có chịu đựng và nuốt được Error văng ra từ ChordNode bị lỗi hay không."""
        # 1. Khởi tạo mạng và Node 20
        transport = LocalTransport()
        node = MockNode(20)
        transport.register(20, node)
        
        # 2. Tạo message độc "BAD" chuyên môn phá hoại Node Handler (raise Exception)
        msg = Message(type="BAD", sender_id=5)
        
        # 3. Gửi message
        response = transport.send(20, msg)
        
        # 4. Xác minh Transport đã tự cô lập lỗi, trả về Error Code chứ không sập
        assert response.success is False
        assert response.error == ErrorCode.NODE_UNREACHABLE
        assert "Something went terribly wrong" in response.data.get("details", "")

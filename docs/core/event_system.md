# Core System: Event Logging & Observability

Hệ thống Event Log đóng vai trò là "hộp đen" của mạng Chord, ghi lại mọi hoạt động trao đổi thông điệp giữa các Node để phục vụ việc debug và hiển thị lên Dashboard.

---

## 1. Kiến trúc hiện tại (Current State)

Hiện tại, hệ thống Event hoạt động theo mô hình **Passive Request Logging** (Ghi chép yêu cầu thụ động).

### 1.1. Cấu trúc dữ liệu (Log Entry)
Mỗi bản ghi log trong `Transport.message_log` bao gồm:
- `from`: ID của node gửi.
- `to`: ID của node nhận.
- `type`: Loại thông điệp (`FIND_SUCCESSOR`, `GET`, `PUT`, `NOTIFY`, `PING`,...).
- `payload_keys`: Danh sách các key/field có trong gói tin (để bảo mật, không log toàn bộ nội dung).
- `timestamp`: Thời gian ghi log.

### 1.2. Cơ chế hoạt động
1.  **Tại lớp Transport**: Khi hàm `send()` được gọi, nó sẽ gọi `_log_message()` trước khi thực hiện kết nối mạng.
2.  **Lưu trữ**: Log được lưu trữ trong một danh sách (`List`) tại bộ nhớ RAM của mỗi Node.
3.  **Thu thập (Polling)**: Dashboard định kỳ gọi tới endpoint `/api/messages` của từng Node để lấy các bản ghi log mới (sử dụng tham số `since` để tối ưu hóa).

---

## 2. Hạn chế của hệ thống hiện tại

1.  **Chỉ có một chiều (Request only)**: Dashboard chỉ thấy gói tin đi đâu, không thấy nó quay về như thế nào.
2.  **Điểm mù lỗi (Error Blindness)**: Nếu một node bị sập hoặc timeout, Event Log không ghi nhận trạng thái thất bại này.
3.  **Thiếu ngữ cảnh (Missing Context)**: Không giải thích được "Tại sao" một node lại quyết định forward tới node kia (thiếu lý do định tuyến).

---

## 3. Kế hoạch nâng cấp (Future Improvements Plan) [ CHƯA TRIỂN KHAI ]

Mục tiêu là chuyển đổi từ ghi log đơn thuần sang **Distributed Tracing**.

### Mục tiêu 1: Log chiều về (Bidirectional Logging)
- **Hành động**: Cập nhật `Transport` để ghi log cả khi nhận được `Response`.
- **Lợi ích**: Dashboard có thể vẽ được cả mũi tên phản hồi, giúp người dùng thấy trọn vẹn "vòng đời" của một truy vấn.

### Mục tiêu 2: Bổ sung ngữ cảnh định tuyến (Routing Context)
- **Hành động**: Thêm trường `reason` vào mỗi bản ghi log.
- **Nội dung**: Ghi rõ logic như "Key thuộc range (n, successor]", "Tìm thấy finger gần nhất N...", "Thử lại sau khi node chết".
- **Lợi ích**: Giúp việc giải thích thuật toán Chord trong báo cáo đồ án trở nên trực quan hơn.

### Mục tiêu 3: Hệ thống trạng thái màu sắc (Status Highlighting)
- **Hành động**: Thêm trường `success: bool` và `error_code: string` vào log.
- **Lợi ích**: Dashboard có thể tự động tô màu đỏ cho các chặng bị lỗi, giúp nhận diện ngay lập tức vị trí mạng bị đứt (Churn).

### Mục tiêu 4: Tối ưu hóa hiệu năng log (Log Rotation)
- **Hành động**: Triển khai cơ chế xoay vòng log (chỉ giữ lại 1000 message gần nhất).
- **Lợi ích**: Tránh việc Node bị tràn bộ nhớ khi chạy demo trong thời gian dài.

### Mục tiêu 5: Real-time Visualization based on Events
- **Hành động**: Chuyển đổi logic hiển thị trên Chord Ring từ việc sử dụng `activeTrace` (sau khi xong) sang sử dụng `messages` (thời gian thực).
- **Lợi ích**: Tạo hiệu ứng "gói tin đang bay" (Flying packet effect). Khi một Event `REQUEST` xuất hiện trong log, Dashboard sẽ vẽ ngay một tia sáng chạy giữa 2 node trên vòng tròn, giúp người xem thấy được quá trình định tuyến đang diễn ra ngay lập tức thay vì phải đợi kết quả cuối cùng.

---

## 4. Bảng so sánh nâng cấp

| Tính năng | Hiện tại | Tương lai |
| :--- | :--- | :--- |
| **Phạm vi** | Chỉ Request | Cả Request & Response |
| **Thông tin lỗi** | Không có | Chi tiết (Timeout, 404,...) |
| **Giải thích logic** | Không có | Có (Reason field) |
| **Giao diện Ring** | Vẽ sau khi xong (Trace-based) | Vẽ thời gian thực (Event-based) |
| **Hiệu ứng** | Đứng yên/Hiện cả cụm | Chuyển động/Gói tin đang bay |

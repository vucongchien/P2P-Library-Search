# ADR 003: Chiến lược Xử lý Đa luồng và Tính nhất quán (Concurrency & Consistency)

## 1. Trạng thái (Status)
Đã quyết định (Accepted)

## 2. Bối cảnh (Context)
Trong mạng P2P Chord, các bảng định tuyến (Successor, Predecessor, Finger Table) liên tục được cập nhật thông qua các tiến trình chạy ngầm (`stabilize`, `fix_fingers`). 
Vấn đề đặt ra là: Làm sao để đảm bảo các yêu cầu truy vấn (`find_successor`) không đọc phải trạng thái "không nhất quán" (inconsistent state) khi các bảng này đang trong quá trình cập nhật giữa chừng?

## 3. Quyết định (Decision)
Hệ thống sử dụng mô hình **Single-threaded Event Loop** (thông qua FastAPI/Uvicorn với `workers=1`) cho mỗi Peer Node thay vì sử dụng các cơ chế khóa (Locking) hoặc Snapshot phức tạp.

## 4. Lý do (Rationale)
1.  **Tính nguyên tử (Atomicity) của Python**: Các thao tác gán giá trị cho biến đơn (như `self.successor_id = new_id`) trong Python là nguyên tử ở cấp độ Global Interpreter Lock (GIL).
2.  **Tránh Race Condition**: Bằng cách giới hạn mỗi Node chạy trên một worker duy nhất, chúng ta đảm bảo rằng tại một thời điểm, Node chỉ xử lý hoặc là một yêu cầu mạng, hoặc là một chu kỳ ổn định mạng. Điều này loại bỏ hoàn toàn khả năng xảy ra xung đột truy cập dữ liệu (Race Condition).
3.  **Đơn giản hóa hệ thống**: Tránh được việc sử dụng Mutex/Locks - vốn dễ gây ra tình trạng Deadlock trong các hệ thống phân tán.
4.  **Phù hợp quy mô**: Với số lượng Node và tần suất truy vấn trong đồ án, mô hình này đảm bảo hiệu năng cực tốt mà vẫn giữ được mã nguồn trong sáng, dễ bảo trì.

## 5. Hướng phát triển tương lai (Future Considerations)
Nếu hệ thống cần mở rộng để xử lý hàng vạn truy vấn/giây trên mỗi Node (Multi-threading):
- Triển khai cơ chế **Immutable Snapshots**: Mỗi lần cập nhật sẽ tạo một bản sao mới của bảng định tuyến.
- Sử dụng **Atomic Swapping**: Tráo đổi con trỏ giữa bảng cũ và bảng mới trong một thao tác duy nhất để người đọc luôn thấy trạng thái hoàn chỉnh.

## 6. Hệ quả (Consequences)
- **Ưu điểm**: Đảm bảo tính nhất quán dữ liệu 100% trong mỗi Node. Dễ debug và giải trình thuật toán.
- **Nhược điểm**: Một yêu cầu có thể phải đợi vài mili giây nếu Node đang bận xử lý một yêu cầu khác trước đó (Blocking). Tuy nhiên, độ trễ này là không đáng kể đối với hệ thống DHT.

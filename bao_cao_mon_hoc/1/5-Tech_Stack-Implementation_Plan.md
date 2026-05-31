# 5. Công Nghệ Sử Dụng & Phương Án Triển Khai (Tech Stack & Implementation Plan)

---

## 5.1 Ngôn Ngữ Lập Trình (Programming Language)

*   **Python (phiên bản 3.12+)**
    *   **Lý do lựa chọn**: Python là ngôn ngữ lập trình mạnh mẽ, cú pháp ngắn gọn và hỗ trợ các mô hình lập trình hiện đại như lập trình bất đồng bộ (`async/await`), giúp đẩy nhanh tốc độ thiết kế và thử nghiệm hệ thống phân tán P2P.
    *   **Đặc điểm kỹ thuật sử dụng**:
        *   `dataclasses`: Định nghĩa cấu trúc chuẩn hóa cho các gói tin giao thức `Message` và gói tin phản hồi `Response`, tối ưu hóa việc tuần tự hóa (serialization) sang định dạng JSON.
        *   `typing` (Type Hinting): Rõ ràng hóa kiểu dữ liệu đầu vào và đầu ra của các hàm định tuyến (routing), giúp tránh các lỗi logic tiềm ẩn trong quá trình phát triển.
        *   `asyncio` / `async-await`: Ứng dụng trong việc xây dựng cơ chế giao tiếp mạng phi chặn (non-blocking I/O) giữa các peer.

---

## 5.2 Phương Án Triển Khai (Deployment)

Hệ thống được thiết kế để triển khai đa tiến trình cục bộ (Localhost Processes), mô phỏng mạng P2P thực tế trên một thiết bị vật lý duy nhất.

```
                  ┌─────────────────────────────────┐
                  │        Dashboard Browser        │
                  │       (http://127.0.0.1:9000)   │
                  └────────────────┬────────────────┘
                                   │ HTTP
                  ┌────────────────▼────────────────┐
                  │    Dashboard Aggregator API     │
                  │         (FastAPI - Port 9000)   │
                  └────────────────┬────────────────┘
                                   │ HTTP API Poll
         ┌─────────────────────────┼─────────────────────────┐
         │ HTTP                    │ HTTP                    │ HTTP
┌────────▼────────┐       ┌────────▼────────┐       ┌────────▼────────┐
│   Peer Node 10  │       │   Peer Node 60  │       │  Peer Node 110  │
│  (FastAPI:8001) │       │  (FastAPI:8002) │       │  (FastAPI:8003) │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

*   **Kiến trúc Đa Tiến Trình (Multi-Process Architecture)**:
    *   Mỗi Peer Node được chạy độc lập dưới dạng một tiến trình web server riêng lẻ. Các node lắng nghe trên các cổng HTTP khác nhau (ví dụ: Node 10 chạy ở cổng 8001, Node 60 chạy ở cổng 8002, v.v.).
    *   **Tách biệt Terminal (Multi-Window Demo)**: Thông qua script điều khiển `demo_split.py`, hệ thống tự động mở độc lập các cửa sổ dòng lệnh (Command Prompt/Terminal) cho từng tiến trình Peer Server và Dashboard Aggregator API (`start cmd /k`). 
        *   *Ý nghĩa thiết kế*: Việc cô lập log đầu ra (`stdout`/`stderr`) của từng tiến trình giúp dễ dàng giám sát vết định tuyến và các traceback lỗi. Đồng thời, giải pháp này giải quyết triệt để lỗi nghẽn ngầm (deadlock) luồng xuất của Windows khi quản lý quá nhiều tiến trình con bằng một cửa sổ chính.
*   **Web Dashboard Deployment**:
    *   Ứng dụng frontend SPA React được xây dựng thành bộ tệp tĩnh tối ưu (HTML, CSS, JS) trong thư mục `dist`.
    *   Tiến trình Dashboard Server (FastAPI) kiêm nhiệm vai trò serve toàn bộ thư mục tĩnh này tại cổng trung tâm 9000. Người dùng chỉ cần khởi chạy hệ thống và truy cập một cổng duy nhất để giám sát toàn bộ mạng P2P.

---

## 5.3 Thư Viện & Khung Làm Việc (Libraries & Frameworks)

### A. Ngăn xếp công nghệ Backend & Core P2P

*   **FastAPI & Uvicorn**:
    *   **FastAPI**: Được sử dụng để tạo các Web API Endpoint cho từng Peer Node (`/message` nhận các thông điệp P2P định tuyến qua HTTP POST, `/join`, `/stabilize`, `/publish`, `/query`) và xây dựng API Gateway cho Dashboard Server. FastAPI tận dụng cơ chế lập trình bất đồng bộ hiệu năng cao giúp xử lý đồng thời nhiều truy vấn gửi đến.
    *   **Uvicorn**: Đóng vai trò máy chủ ASGI (Asynchronous Server Gateway Interface) trực tiếp vận hành các ứng dụng FastAPI.
*   **HTTPX**:
    *   Đóng vai trò là HTTP Client trong `NetworkTransport` để gửi các yêu cầu POST JSON giữa các node với nhau khi định tuyến trong Chord ring.
    *   *Connection Pooling*: HTTPX được thiết lập connection pool (`limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)`) giúp duy trì và tái sử dụng các kết nối TCP hiện có giữa các Peer, giảm đáng kể thời gian trễ do bắt tay TCP (TCP handshake) gây ra.
*   **Pydantic**:
    *   Khung kiểm tra dữ liệu và ép kiểu mạnh (data validation) cho các tham số đầu vào của API, đảm bảo các tin nhắn JSON nhận được khớp chính xác với cấu trúc định nghĩa trong `models.py`.
*   **Pytest**:
    *   Được sử dụng làm framework chính để thực hiện kiểm thử tự động (Unit Test / Integration Test). Đảm bảo tính ổn định và chính xác của thuật toán Chord, tính toán hash, định tuyến finger table và khả năng tự hồi phục khi có biến động thành viên.

### B. Ngăn xếp công nghệ Frontend (Dashboard)

*   **React 19 & Vite**:
    *   **React 19**: Framework xây dựng giao diện người dùng SPA (Single Page Application). Quản lý trạng thái và kết xuất động topo mạng, biểu đồ lưu lượng tin nhắn, và danh sách khóa DHT.
    *   **Vite**: Công cụ build frontend thế hệ mới mang lại tốc độ biên dịch và hot-reload cực nhanh trong quá trình phát triển.
*   **Tailwind CSS 4.2.2**:
    *   CSS framework hiện đại dùng để thiết kế giao diện dashboard trực quan (đồ thị mạng trực tuyến, bảng phân bổ khóa DHT primary/replica), hỗ trợ dark mode, responsive layout và các micro-animations mượt mà cho trải nghiệm người dùng cao cấp.
*   **Lucide React**:
    *   Bộ thư viện biểu tượng (icon) vector dạng SVG sắc nét, tích hợp mượt mà vào React giúp tối giản hóa mã nguồn giao diện.

# Chiến lược Commit & Kiểm thử - P2P Library Search

Tài liệu này định nghĩa cách thức quản lý mã nguồn (Git) và quy trình đảm bảo chất lượng (QA) cho hệ thống P2P Search dựa trên thuật toán Chord DHT.

---

## I. Chiến lược Commit (Commit Strategy)

Áp dụng quy tắc **Conventional Commits** kết hợp với tư duy **Atomic Commits** (Commit nguyên tử).

### 1. Cấu trúc Commit Message
```text
<type>(<scope>): <subject>

<body>
[Tùy chọn: Giải thích logic hoặc trade-off]

<footer>
[Tùy chọn: Fixes #issue_id]
```

### 2. Các Loại (Types) & Phạm vi (Scopes) phổ biến trong dự án
| Type | Scope | Ví dụ mô tả |
| :--- | :--- | :--- |
| `feat` | `chord` | Cài đặt thuật toán `stabilize` và `fix_fingers` |
| `feat` | `query` | Thêm logic `Early Stop` cho truy vấn AND |
| `fix` | `routing` | Sửa lỗi Routing Loop khi Successor List bị rỗng |
| `test` | `storage` | Thêm unit test kiểm tra Data Handoff khi Node Join |
| `refactor`| `transport` | Tách `NetworkTransport` ra khỏi logic của `ChordNode` |
| `docs` | `report` | Cập nhật báo cáo về khả năng chịu lỗi (Churn Resilience) |

### 3. Ví dụ một Commit chuẩn Production
```text
feat(query): implement distributed AND query with early-stop logic

- Thêm QueryEngine xử lý băm từ khóa và định tuyến tới các node chứa index.
- Cài đặt cơ chế Early Stop: Nếu một từ khóa không có kết quả, dừng ngay lập tức để tiết kiệm hop mạng.
- Đi kèm unit test trong tests/test_query_engine.py

Trade-off: Tăng độ phức tạp của mã nguồn nhưng giảm ~40% message overhead cho các truy vấn rỗng.
```

---

## II. Chiến lược Kiểm thử (Testing Strategy)

Hệ thống P2P rất dễ bị lỗi lan truyền (Propagation error). Chúng ta sẽ kiểm thử theo mô hình hình tháp.

### 1. Tầng 1: Unit Testing (Trọng tâm)
*   **Mục tiêu**: Kiểm tra logic thuật toán tại từng node độc lập.
*   **Các module cần phủ kín test**:
    *   `src/chord/routing_mixin.py`: Test `find_successor`, `closest_preceding_node`.
    *   `src/models/id_space.py`: Test hàm `in_range` (đặc biệt là trường hợp vắt ngang điểm 0 của Ring).
    *   `src/chord/storage_mixin.py`: Test việc gộp (Merge) Inverted Index.

### 2. Tầng 2: Integration Testing (Chord Ring)
*   **Mục tiêu**: Kiểm tra sự tương tác giữa các node trong môi trường `LocalTransport`.
*   **Kịch bản**:
    *   **Ring Formation**: Join 5-10 node vào mạng, kiểm tra xem Successor của mỗi node có trỏ đúng vào node tiếp theo theo thứ tự ID không.
    *   **Data Consistency**: Thực hiện `PUT` keyword "A" vào node 10, kiểm tra xem node chịu trách nhiệm (ví dụ node 15) có nhận được dữ liệu không.

### 3. Tầng 3: Churn & Resilience Testing (Stress Test)
*   **Mục tiêu**: Kiểm tra hệ thống khi có sự cố.
*   **Công cụ**: Sử dụng `src/churn_simulation.py`.
*   **Kịch bản "Kill-Node"**:
    1. Chạy hệ thống ổn định with 10 nodes.
    2. Tắt đột ngột 2 node bất kỳ (có chứa dữ liệu quan trọng).
    3. Đợi 3 chu kỳ `stabilize`.
    4. Thực hiện lại truy vấn. **Kết quả đạt**: 100% dữ liệu phải được phục hồi từ Replicas.

### 4. Tầng 4: Network & API Testing
*   **Mục tiêu**: Kiểm tra trên môi trường FastAPI thật.
*   **Hành động**:
    *   Sử dụng `peer_server.py` để dựng các process thật.
    *   Test xử lý lỗi khi `NetworkTransport` gặp lỗi `ConnectionRefused` (Simulate network partition).
    *   Kiểm tra Tracing log tại `results/traces/` để đảm bảo hop-count thực tế khớp với lý thuyết O(log N).

---

## III. Quy trình Thực thi (Implementation Workflow)

1.  **Viết Test trước (TDD)**: Khi thêm tính năng định tuyến mới, hãy viết test case giả lập topology ring trước.
2.  **Đọc Log & Fix**: Nếu test fail, quan sát `message_log` của Transport để tìm node gây lỗi.
3.  **Commit**: Sau khi pass hết các test liên quan, thực hiện commit theo chuẩn đã đề ra.
4.  **Tài liệu**: Cập nhật file `.md` trong thư mục `tests/` để mô tả các test case mới thêm vào.

> [!IMPORTANT]
> Tuyệt đối không commit code khi chưa pass Unit Test. Hệ thống P2P rất khó debug nếu lỗi nằm ở logic cơ bản của Ring.

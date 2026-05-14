# Core Algorithm: Distributed Query Engine

Tài liệu này mô tả chi tiết thuật toán truy vấn được cài đặt trong `QueryEngine` của hệ thống P2P Library Search.

---

## 1. Tổng quan
Hệ thống hỗ trợ truy vấn từ khóa kết hợp (Multi-keyword search) theo toán tử **AND**. 
Mục tiêu chính: **Tối thiểu hóa số lượng thông điệp mạng (Network Overhead)** và **Đảm bảo tính chính xác của dữ liệu (Data Integrity)** trong môi trường phân tán.

## 2. Các thành phần chính
- **Initiator (Nút khởi tạo)**: Node nhận yêu cầu từ người dùng.
- **Chord DHT**: Giao thức định tuyến để tìm node chứa Inverted Index của một từ khóa.
- **Inverted Index**: Bảng chỉ mục ngược lưu trữ bộ `{keyword: [doc_id1, doc_id2, ...]}`.
- **Incremental Intersect**: Kỹ thuật giao các tập kết quả theo từng bước.

---

## 3. Quy trình Thuật toán (Step-by-Step)

### Bước 1: Tiền xử lý (Preprocessing)
1. Chuyển truy vấn về chữ thường (lowercase).
2. Tách chuỗi thành danh sách các từ khóa độc lập. Loại bỏ các từ dừng (stopwords) hoặc từ khóa "and".
   - *Ví dụ*: `"System AND Database"` -> `["system", "database"]`.

### Bước 2: Vòng lặp Truy vấn Tăng dần (Incremental Fetch)
Với mỗi từ khóa $K_i$ trong danh sách:

1. **Định tuyến (Routing)**: Initiator băm từ khóa $H = \text{hash}(K_i)$ và sử dụng bảng Finger Table để tìm node $N_{resp}$ chịu trách nhiệm quản lý ID $H$.
2. **Lấy dữ liệu (Fetch)**: Gửi thông điệp `GET(K_i)` tới node $N_{resp}$.
3. **Nhận kết quả**: $N_{resp}$ trả về `Posting List` (danh sách ID tài liệu) kèm theo `Routing Trace` (dấu vết đường đi thực tế).

### Bước 3: Giao tập hợp (Intersection)
- Duy trì một tập kết quả tạm thời `FinalSet`.
- Với từ khóa đầu tiên: `FinalSet = PostingList(K_1)`.
- Với các từ khóa tiếp theo: `FinalSet = FinalSet ∩ PostingList(K_i)`.

### Bước 4: Chiến lược Ngắt sớm (Early Stop) - [QUAN TRỌNG]
Nếu tại bất kỳ bước nào, `FinalSet` trở thành **Rỗng (Empty)**:
- Hệ thống lập tức dừng việc truy vấn các từ khóa còn lại trong danh sách.
- **Lý do**: Trong phép toán AND, nếu một thành phần đã rỗng thì kết quả cuối cùng chắc chắn là rỗng. Việc fetch tiếp các từ khóa sau là lãng phí tài nguyên mạng.

---

## 4. Đặc tính kỹ thuật

### 4.1. Source of Truth Tracing
Thay vì suy đoán đường đi, mỗi node trong lộ trình định tuyến sẽ tự ghi thông tin của mình vào `RoutingTrace` đính kèm trong response. 
- **Lợi ích**: Đảm bảo số lượng Hops và danh sách các Node trung gian là chính xác 100%, phục vụ việc phân tích hiệu năng.

### 4.2. Xử lý Churn (Lỗi mạng)
Nếu việc fetch một từ khóa thất bại (node chết):
- Hệ thống đánh dấu trạng thái là `PARTIAL_DATA`.
- Vẫn tiếp tục thực hiện giao các tập kết quả đã lấy được (nếu có) để trả về kết quả tốt nhất có thể kèm theo cảnh báo.

---

## 5. Minh họa luồng (Mermaid)

```mermaid
graph TD
    A[Start Query: 'A AND B'] --> B{Keyword list: [A, B]}
    B --> C[Fetch Keyword A via Chord]
    C --> D[Result A: {Doc1, Doc2, Doc3}]
    D --> E[FinalSet = {Doc1, Doc2, Doc3}]
    E --> F[Fetch Keyword B via Chord]
    F --> G[Result B: {Doc2, Doc4}]
    G --> H[FinalSet = FinalSet ∩ {Doc2, Doc4}]
    H --> I{FinalSet is empty?}
    I -- No --> J[Return {Doc2}]
    I -- Yes --> K[Early Stop & Return Empty]
```

---

## 6. Trade-offs (Đánh đổi)
- **Ưu điểm**: Cực kỳ tiết kiệm băng thông khi gặp từ khóa hiếm (vì sẽ trigger Early Stop nhanh chóng).
- **Nhược điểm**: Thời gian phản hồi (Latency) phụ thuộc vào tổng số từ khóa vì thực hiện tuần tự (Sequential). Có thể tối ưu bằng cách fetch song song (Parallel Fetch) nhưng sẽ mất đi lợi thế của Early Stop. Hiện tại ưu tiên giảm Overhead mạng.

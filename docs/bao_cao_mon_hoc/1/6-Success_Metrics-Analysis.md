# 6. Success Metrics & Analysis (Đo Lường Hiệu Năng & Phân Tích)

---

## 6.1 Chỉ Số Định Lượng (Quantitative Metrics)

Hệ thống sử dụng các chỉ số định lượng sau để đo lường hiệu năng, độ tin cậy và tính đúng đắn trên môi trường mạng HTTP thực tế (được thu thập qua API `/api/query` của các Peer và Dashboard Aggregator):

### 1. Tổng Thời Gian Thực Thi Truy Vấn (Query Latency)
- **Đơn vị đo**: Mili giây ($ms$).
- **Mô tả**: Được tính từ thời điểm Node khởi tạo (Initiator Peer) nhận được yêu cầu truy vấn từ Dashboard, thực hiện tách từ khóa, định tuyến Chord DHT qua HTTP POST để lấy Posting List của từng từ khóa, thực hiện giao tập (AND Intersection) tuần tự, cho đến khi trả về kết quả cuối cùng.
- **Ý nghĩa**: Phản ánh tốc độ phản hồi thực tế của hệ thống. Độ trễ này chịu ảnh hưởng lớn bởi số lượng từ khóa trong câu truy vấn, số bước nhảy định tuyến (Hops) và độ trễ mạng loopback HTTP ($127.0.0.1$).

### 2. Độ Chính Xác & Nhất Quán của Kết Quả (Query Accuracy & Consistency)
- **Đơn vị đo**: Tỷ lệ khớp phần trăm ($0\% - 100\%$).
- **Mô tả**: So sánh danh sách `DocIDs` trả về từ công cụ truy vấn phân tán với danh sách `DocIDs` thu được bằng phương pháp tìm kiếm tuần tự brute-force (Ground Truth) trên tập dữ liệu gốc 100 truyện ngắn.
- **Ý nghĩa**: Đảm bảo thuật toán phân tán không làm mất mát dữ liệu. Đặc biệt, hệ thống tiến hành đối chiếu kết quả truy vấn **trước và sau sự cố Churn** (Node chết đột ngột). Tỷ lệ khớp phải đạt **$100\%$** để chứng minh tính nhất quán dữ liệu dưới tác động của sự cố.

### 3. Số Bước Nhảy Định Tuyến (Routing Hops)
- **Đơn vị đo**: Số lần chuyển tiếp tin nhắn (Hops).
- **Mô tả**: Số lượng node trung gian thực tế mà yêu cầu định tuyến cần đi qua để tìm đến successor chịu trách nhiệm cho hash của từ khóa (trích xuất từ `routing_trace` in-band).
- **Ý nghĩa**: Kiểm chứng hiệu năng thuật toán Finger Table của Chord. Với mạng gồm $N=5$ nodes, số bước nhảy tối đa lý thuyết là $\log_2(5) \approx 2.3$ hops.

### 4. Băng Thông & Tải Tin Nhắn (Query Message Overhead)
- **Đơn vị đo**: Số lượng tin nhắn mạng (Messages).
- **Mô tả**: Tổng số lượng tin nhắn HTTP gửi đi giữa các node trong suốt quá trình xử lý câu truy vấn.
- **Ý nghĩa**: Đánh giá hiệu quả của cơ chế **Early Stop Optimization**. Khi một từ khóa trung gian trả về tập kết quả rỗng ($\emptyset$), truy vấn AND lập tức dừng lại, giúp số lượng tin nhắn thực tế giảm đáng kể so với việc định tuyến và fetch Posting List của toàn bộ từ khóa.

---

## 6.2 Kịch Bản Giả Lập Sự Cố (Failure Scenario - Node Churn)

Để chứng minh khả năng chịu lỗi và tính tự chữa lành của hệ thống, chúng ta thực hiện mô phỏng sự cố **ngắt kết nối một node đột ngột** trên môi trường chạy thực tế của `demo_split.py`.

```
                    ┌──────────────────────────┐
                    │     Mạng 5 Nodes thường  │
                    │   N10, N60, N110, N160,  │
                    │           N210           │
                    └─────────────┬────────────┘
                                  │
                       [ Tắt CMD của Node 60 ]
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │    Node 60 Offline       │
                    │  (Dashboard báo đèn đỏ)  │
                    └─────────────┬────────────┘
                                  │
                    [ Gửi Query từ Node 10 ] (Chứa stale finger trỏ tới N60)
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ HTTP POST -> N60 thất bại│
                    │   (Connection Refused)   │
                    └─────────────┬────────────┘
                                  │
                        [ Routing Fallback ] (N10 định tuyến qua successor kế tiếp N110)
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │    Replica Promotion     │
                    │ N110 thăng cấp bản sao   │
                    │    của N60 thành công    │
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ Kết quả trả về đúng 100% │
                    │    (Không mất dữ liệu)   │
                    └─────────────┬────────────┘
                                  │
                [ Thread bảo trì chạy ngầm (5s) ] (Ổn định lại Topo Ring)
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │     Mạng 4 Nodes ổn định │
                    │    N10 -> N110 -> N160   │
                    │          -> N210         │
                    └──────────────────────────┘
```

### Bước 1: Trạng Thái Bình Thường (Baseline)
- Mạng hoạt động ổn định với 5 node: `N10`, `N60`, `N110`, `N160`, `N210`. Dữ liệu 100 truyện ngắn đã được chia đều và index vào DHT.
- Các từ khóa như `"system"` và `"database"` có hash rơi vào vùng quản lý của `N60` (lưu primary dht_store). Dữ liệu này được nhân bản (replicate) sang successor của nó là `N110` (lưu replica_store).
- Người dùng thực hiện truy vấn `"system AND database"` từ node `N10`.
- **Kết quả Baseline**: Truy vấn thành công, trả về danh sách tài liệu khớp (ví dụ: `DocID 10`), thời gian phản hồi thấp ($~10-20ms$), số bước nhảy định tuyến tối ưu.

### Bước 2: Kích Hoạt Sự Cố (Un-graceful Node Failure)
- Người dùng chủ động **tắt cửa sổ CMD của `Peer Node 60`** (bằng cách bấm dấu `[X]`). Tiến trình uvicorn tại cổng `8002` lập tức dừng hoạt động. Đây là sự cố sập node đột ngột (không qua thủ tục rời mạng an toàn).
- Dashboard Backend nhận diện `N60` mất kết nối và hiển thị trạng thái Offline (màu đỏ) trên giao diện.
- Người dùng nhấn nút xóa Node 60 trên dashboard, gọi API `/api/churn/remove` để các node còn sống cập nhật danh bạ mạng (`Transport Registry`), tránh lãng phí tài nguyên gửi tin nhắn. Lúc này, finger table của các node còn sống (như `N10`) vẫn còn chứa con trỏ trỏ tới `N60`.

### Bước 3: Cơ Chế Chịu Lỗi & Phục Hồi Dữ Liệu Tức Thời
- Người dùng thực hiện lại truy vấn `"system AND database"` từ `N10` **ngay lập tức** (trước khi vòng lặp bảo trì chạy ngầm kịp cập nhật ring).
- **Diễn biến xử lý**:
  1. `N10` cố gắng gửi HTTP POST `/message` đến `N60` (cổng `8002`) dựa trên Finger Table cũ.
  2. Transport layer báo lỗi `NODE_UNREACHABLE` (Connection Refused) vì tiến trình của `N60` đã bị kill.
  3. Chord layer tại `N10` bắt được lỗi kết nối, kích hoạt hàm xử lý lỗi định tuyến `_handle_routing_failure()`. `N10` tạm thời bỏ qua `N60`, định tuyến qua các finger khác hoặc chuyển tiếp trực tiếp đến successor còn sống gần nhất của nó là `N110`.
  4. Yêu cầu truy vấn keyword `"system"` và `"database"` chuyển đến `N110`.
  5. `N110` kiểm tra và phát hiện các keyword này nằm trong `replica_store` (bản sao lưu từ predecessor `N60` trước đó). `N110` tiến hành **Replica Promotion** (thăng cấp dữ liệu bản sao lên xử lý) và trả ngược Posting List về cho `N10`.
- **Kết quả truy vấn**: Câu truy vấn hoàn thành xuất sắc, trả về danh sách `DocIDs` trùng khớp $100\%$ so với trạng thái Baseline (không bị mất mát tài liệu tìm kiếm), chứng minh tính chịu lỗi tức thời của hệ thống.

### Bước 4: Tự Chữa Lành Mạng (Self-Healing)
- Các tiến trình peer còn lại chạy với cờ `--auto-stabilize` có các thread chạy ngầm bảo trì định kỳ mỗi 5 giây.
- Chỉ sau tối đa 5 giây từ khi sự cố xảy ra, các thread này tự động kích hoạt:
  - `node.stabilize()`: Phát hiện successor trực tiếp (`N60`) đã chết, tự động kết nối và nhận `N110` làm successor mới.
  - `node.fix_fingers()`: Cập nhật lại các pointer trong Finger Table, loại bỏ hoàn toàn các con trỏ trỏ đến địa chỉ của `N60`.
  - `node.maintain_data()`: Node `N110` chính thức tiếp quản dứt điểm dữ liệu của `N60`, đồng thời gửi bản sao lưu mới sang successor của nó (`N160`) để đảm bảo hệ số dự phòng.
- Khi người dùng truy vấn lại lần thứ ba, đường đi định tuyến đã được tối ưu hóa trực tiếp (không còn đi qua con đường lỗi của `N60`), thời gian phản hồi (Latency) quay về mức tối ưu ban đầu.

---

## 6.3 Phân Tích Trade-offs (Thỏa Hiệp Thiết Kế)

Kiến trúc phân tán của hệ thống được xây dựng dựa trên sự cân bằng giữa 3 thỏa hiệp kỹ thuật quan trọng sau:

| Thiết Kế Được Chọn | Ưu Điểm (Chọn) | Nhược Điểm (Bỏ qua) | Lý Do Thỏa Hiệp |
| :--- | :--- | :--- | :--- |
| **Bảo trì ngầm định kỳ 5 giây** (`--auto-stabilize` thread) | Giảm thiểu băng thông nền (background traffic) cho mạng P2P; tránh nghẽn mạng do tin nhắn bảo trì liên tục. | Thời gian cập nhật topo mạng chậm hơn khi có sự cố Churn, tạo ra các "stale finger table" tạm thời trong khoảng tối đa 5 giây. | Quy mô demo nhỏ ($5$ nodes) cho phép chấp nhận trễ 5 giây. Cơ chế chịu lỗi tại chỗ (Routing Fallback) đã bù đắp được khoảng trễ này để đảm bảo dịch vụ không gián đoạn. |
| **Hệ số nhân bản bản sao $r=2$** (Lưu 1 Primary, 1 Backup ở Successor) | Tiết kiệm băng thông ghi (`PUT`) và dung lượng bộ nhớ RAM của mỗi peer; thiết kế đơn giản, dễ duy trì tính nhất quán. | Chỉ chịu được tối đa $1$ node chết đột ngột tại một thời điểm trong phân đoạn mạng ring. Nếu 2 node liền kề cùng sập (double failure) trước khi kịp stabilize, dữ liệu sẽ bị mất. | Trong điều kiện vận hành thực tế của thư viện số nội bộ, xác suất 2 node liền kề chết đồng thời trong khoảng thời gian bảo trì 5 giây là cực kỳ thấp. Hệ số $r=2$ là điểm cân bằng tối ưu giữa an toàn và chi phí. |
| **Truy vấn AND tuần tự + Early Stop** (Giao tập từng bước) | Tiết kiệm tối đa băng thông mạng. Khi một từ khóa trả về kết quả rỗng ($\emptyset$), hệ thống dừng ngay lập tức, không cần định tuyến và fetch Posting List của các từ khóa còn lại. | Làm tăng tổng độ trễ truy vấn (Query Latency) đối với các câu truy vấn thành công có nhiều từ khóa, do phải thực hiện các cuộc gọi HTTP tuần tự thay vì song song. | Trong tìm kiếm văn bản, tỷ lệ truy vấn có chứa từ khóa không tồn tại hoặc giao tập rỗng là khá phổ biến. Việc tối ưu hóa băng thông bằng Early Stop mang lại lợi ích lớn hơn nhiều so với việc tối ưu hóa độ trễ cho các truy vấn song song phức tạp. |

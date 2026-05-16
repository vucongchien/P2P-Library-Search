# Dashboard Auto-Refresh Logic

Tài liệu này tóm tắt các công việc được thực hiện bởi chức năng Auto-Refresh (Polling) trên Dashboard.

## 1. Cơ chế hoạt động
- **Hook chính**: `useRingState` (nằm trong `dashboard/frontend/src/hooks/useRingState.js`).
- **Interval**: Mặc định là **2000ms (2 giây)**.
- **Trạng thái kích hoạt**: Được điều khiển bởi biến `isPolling`. Khi bật, Dashboard sẽ tự động gọi hàm `fetchState` định kỳ.

## 2. Các công việc thực hiện (Workflow)
Mỗi chu kỳ refresh, frontend sẽ thực hiện các request tới Backend Aggregator. Dưới đây là chi tiết xử lý của cả hai phía:

### A. Cập nhật danh sách Peer (`/api/peers`)
- **Frontend**: Gọi `api.getPeers()` để cập nhật danh sách node và trạng thái Online/Offline.
- **Backend**: 
    - Lặp qua danh sách node đã cấu hình.
    - Gửi request `/health` tới từng Peer Server để kiểm tra độ sống.
    - Trả về danh sách kèm trạng thái `alive`.

### B. Cập nhật trạng thái Ring (`/api/ring-state`)
- **Frontend**: Gọi `api.getRingState()` để lấy dữ liệu vẽ Network Graph.
- **Backend**:
    - Gọi `/api/state` tới **tất cả** các Peer đang chạy.
    - Tổng hợp thông tin về Predecessor, Successor, và Finger Table.
    - Xử lý lỗi (skip) nếu có Peer không phản hồi để không làm treo Dashboard.

### C. Thu thập Metrics (`/api/metrics`)
- **Frontend**: Gọi `api.getMetrics()` để cập nhật các chỉ số thống kê (Stats cards).
- **Backend**:
    - Gọi `/api/state` và trích xuất phần `stats`.
    - Cộng dồn các chỉ số: `total_messages`, `total_dht_keys`, `total_replica_keys`.
    - Tính toán lưu lượng (traffic) riêng biệt cho từng Peer.

### D. Lấy Log Messages (`/api/messages/all`)
- **Frontend**: Gọi `api.getMessages()` với cơ chế incremental (chỉ lấy tin mới).
- **Backend**:
    - Sử dụng `msg_cursors` (biến lưu vết trong bộ nhớ backend) để biết đã lấy đến dòng log nào của từng Peer.
    - Gọi `/api/messages?since={cursor}` tới từng Peer.
    - Gán nhãn `_peer_source` cho mỗi bản tin để biết log đó của node nào.
    - Sắp xếp tất cả bản tin theo timestamp trước khi trả về.

### E. Cập nhật Timestamp
- **Frontend**: Sau khi hoàn thành các lệnh gọi API, Dashboard cập nhật `lastUpdated` để người dùng biết dữ liệu vừa được làm mới.

## 3. Cơ chế chống Polling Spam
Để đảm bảo Dashboard không làm quá tải hệ thống P2P, các cơ chế sau đã được triển khai:
- **Interval Control**: Giới hạn polling tối thiểu 2 giây.
- **Incremental Logging**: Backend và Peer chỉ trao đổi những bản tin log mới phát sinh dựa trên `cursor`, thay vì gửi toàn bộ lịch sử log.
- **Concurrent Requests**: Backend Aggregator gọi các Peer một cách độc lập, lỗi của một Peer không ảnh hưởng đến dữ liệu của các Peer khác.
- **Short Timeouts**: Các request từ Dashboard tới Peer có timeout ngắn (mặc định 5s) để tránh việc Dashboard bị treo khi có node chết.

## 4. Ý nghĩa đối với hệ thống P2P
- **Quan sát thời gian thực**: Theo dõi quá trình tự ổn định (self-healing) của vòng Chord.
- **Debug trực quan**: Theo dõi luồng tin nhắn di chuyển giữa các node khi thực hiện Query.
- **Giám sát phân bổ dữ liệu**: Theo dõi số lượng Key (dht_keys) trên từng node để kiểm tra tính cân bằng của mã băm (hashing).

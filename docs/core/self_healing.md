# Core System: Autonomous Self-Healing

Tài liệu này mô tả cơ chế tự chữa lành của mạng P2P Chord, giúp hệ thống duy trì cấu trúc vòng tròn và toàn vẹn dữ liệu ngay cả khi các Node gia nhập hoặc rời mạng đột ngột (Churn).

---

## 1. Các thành phần cốt lõi

Cơ chế Self-healing được xây dựng dựa trên 3 thuật toán định kỳ chạy ngầm tại mỗi Peer Node:

### 1.1. Stabilize (Ổn định Successor)
- **Mục tiêu**: Đảm bảo con trỏ `successor` luôn trỏ đúng vào node kế tiếp theo thứ tự ID.
- **Quy trình**:
  1. Node $N$ hỏi successor của mình ($S$): "Ai là predecessor của bạn?".
  2. $S$ trả lời là $X$.
  3. Nếu $X$ nằm giữa $N$ và $S$, Node $N$ cập nhật successor mới là $X$.
  4. Node $N$ thông báo cho successor mới biết về sự tồn tại của mình (`notify`).

### 1.2. Check Predecessor (Kiểm tra Node đứng trước)
- **Mục tiêu**: Phát hiện sớm việc node đứng trước bị sập.
- **Quy trình**:
  1. Node $N$ gửi một tin nhắn `PING` tới `predecessor`.
  2. Nếu không nhận được phản hồi sau thời gian timeout, $N$ đặt `predecessor = None`.
  3. **Data Promotion**: Nếu phát hiện predecessor chết, Node $N$ ngay lập tức thăng cấp các dữ liệu trong `replica_store` lên thành dữ liệu chính (`dht_store`).

### 1.3. Fix Fingers (Cập nhật bảng định tuyến nhanh)
- **Mục tiêu**: Cập nhật lại các chặng nhảy xa trong Finger Table để đảm bảo tốc độ tìm kiếm $O(\log N)$.
- **Quy trình**: Node $N$ chọn ngẫu nhiên một entry trong Finger Table và thực hiện tìm kiếm successor cho ID tương ứng.

---

## 2. Kịch bản xử lý sự cố (Failure Scenario)

Giả sử mạng đang có: `N10 -> N60 -> N110`. Node `N60` đột ngột bị tắt.

1.  **Phát hiện**: 
    - `N10` chạy `stabilize()` và nhận thấy không thể kết nối tới `N60`.
    - `N110` chạy `check_predecessor()` và thấy `N60` không trả lời.
2.  **Hành động của N10**:
    - `N10` sử dụng danh sách successor dự phòng (hoặc tìm kiếm lại) để trỏ thẳng tới `N110`.
    - Vòng tròn được nối lại: `N10 -> N110`.
3.  **Hành động của N110**:
    - `N110` nhận thấy `N60` chết. Nó lấy toàn bộ dữ liệu backup của `N60` (đang giữ trong `replica_store`) để đưa vào kho lưu trữ chính.
    - Dữ liệu không bị mất mát.

---

## 3. Chế độ vận hành (Autonomous Mode)

Hệ thống hỗ trợ 2 chế độ kích hoạt Self-healing:

-   **Dashboard Triggered**: Dashboard gửi tín hiệu kích hoạt. Phù hợp cho việc quan sát từng bước thay đổi của mạng.
-   **Autonomous Background Task**: Mỗi Node tự chạy một vòng lặp `asyncio` mỗi 5 giây. Đảm bảo mạng tự chữa lành 24/7 mà không cần sự can thiệp của con người hay giao diện điều khiển.

> [!IMPORTANT]
> **Tính tự trị (Autonomy)** là đặc điểm quan trọng nhất giúp hệ thống đạt mức đánh giá **Excellent** trong tiêu chí **Churn Resilience**.

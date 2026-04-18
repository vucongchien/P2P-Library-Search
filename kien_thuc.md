👉 Mọi design đều xoay quanh:
giảm số message
giảm kích thước message
giảm số hop

---
ko dùng flooding, chúng ta dùng DHT;
consitent hashing là nền tảng của DHT;
kiến trúc share-nothing;

# Chord:
    Mỗi node không chỉ biết hàng xóm
    → nó biết các node ở xa hơn theo cấp số nhân

    Công thức:
        finger[i]=successor(n+2^(i-1))
        - successor(x) = node đầu tiên theo chiều kim đồng hồ có ID ≥ x

# Chord là gì?

Chord = một thuật toán cụ thể để làm DHT

Nó trả lời mấy câu mà DHT bỏ trống:

Vấn đề | Chord trả lời
key đi đâu? | consistent hashing lên ring
node nào giữ key? | successor của key
tìm node kiểu gì? | finger table → O(log N)
node join? | update successor/predecessor
node chết? | stabilize + fix_fingers


# 1. Consistent Hashing (Cốt lõi)

Không gian ID là một vòng tròn (ring) từ 0 đến 2^m - 1.

- **Mỗi node** được gán một ID duy nhất trên vòng tròn này.
- **Mỗi key** (từ dữ liệu) cũng được băm ra một ID trên vòng tròn.
- **Quy tắc:** Một key thuộc về node **successor** của nó (node đầu tiên theo chiều kim đồng hồ có ID ≥ key ID).

# 2. Finger Table (Bảng ngón tay)

Để tìm key trong O(log N) thay vì O(N) (duyệt tuần tự), mỗi node giữ một **finger table**.

- Finger[i] trỏ đến node tiếp theo có ID ≥ (n + 2^(i-1)) mod 2^m.
- Với m = 32, mỗi node chỉ cần lưu 32 con trỏ.

# 3. Tìm kiếm (Lookup)

Để tìm node giữ key `k`:

1. Bắt đầu từ node hiện tại `n`.
2. Kiểm tra xem `k` có nằm giữa `n` và `finger[1]` không.
3. Nếu có → chuyển sang `finger[1]`.
4. Nếu không → chuyển sang `finger[i]` lớn nhất mà `finger[i]` vẫn < `k`.
5. Lặp lại cho đến khi tìm thấy.

Độ phức tạp: O(log N).

# 4. Node Join

Khi node mới `n` gia nhập:

1. Tìm vị trí của `n` trên ring (hỏi successor của node bất kỳ).
2. Khởi tạo finger table của `n` (hỏi successor của các mốc 2^i).
3. Thông báo cho các node khác cập nhật finger table của chúng.
4. Di chuyển dữ liệu cần thiết từ successor sang `n`.

# 5. Node Leave / Fail

Khi node rời đi:

1. Thông báo cho successor để nó cập nhật successor pointer.
2. Di chuyển dữ liệu của node rời sang successor.
3. Các node khác cập nhật bằng việc gọi hàm lookup để cập nhật finger table khi tìm kiếm.

# 6. Stabilize (Ổn định)

Để đảm bảo tính đúng đắn khi node join/leave, mỗi node định kỳ chạy `stabilize()`:

1. Hỏi successor của nó: "Ai là predecessor của bạn?"
2. Nếu predecessor đó nằm giữa `n` và `successor`, cập nhật `finger[1]` của `n`.
3. Thông báo cho successor: "Tôi là predecessor của bạn".

# 7. Ý nghĩa của Successor và Predecessor

- **Successor** của một node `n` là node đầu tiên theo chiều kim đồng hồ có ID ≥ `n`.
- **Predecessor** của một node `n` là node đầu tiên ngược chiều kim đồng hồ có ID ≤ `n`.

- successor: đảm bảo reachability
- predecessor: đảm bảo correctness boundary

# 9. Handoff data

- khi data join, node join vào giữa 2 node, node join phải nhận data từ successor của nó
- khi data leave, node leave phải chuyển data cho successor của nó


![alt text](/img/image.png)

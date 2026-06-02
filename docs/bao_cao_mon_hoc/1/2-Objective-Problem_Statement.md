# 2. Mục Tiêu & Phát Biểu Vấn Đề

---

## 2.1 Đề Tài Giải Quyết Thách Thức Cụ Thể Nào?

### Hạn Chế của Hệ Thống Tập Trung (Centralized)

Search engine truyền thống lưu toàn bộ inverted index tại một server duy nhất. Kiến trúc này tạo ra các điểm yếu kinh điển trong hệ thống phân tán:

```
         User A ──▶ ┌──────────┐
         User B ──▶ │  SERVER  │ ◀── Toàn bộ index + data
         User C ──▶ └──────────┘
                       ▲
                  Single Point of Failure
```

| Vấn đề | Mô tả |
| --- | --- |
| **SPOF** | Server chết = toàn bộ hệ thống sập, không có dự phòng |
| **Bottleneck** | Mọi truy vấn đều đi qua 1 node duy nhất, tắc nghẽn khi tải cao |
| **Scaling cứng nhắc** | Dữ liệu tăng → phải nâng cấp server vật lý (vertical scaling) |
| **Data Sovereignty** | Toàn bộ tài liệu phụ thuộc vào 1 thực thể kiểm soát |

---

### 3 Thách Thức Kỹ Thuật Cốt Lõi Đề Tài Giải Quyết

#### 🔴 Thách Thức 1 — Phân Tán Chỉ Mục (Distributed Indexing)

> *"Làm thế nào lưu inverted index của hàng nghìn từ khóa mà không cần server trung tâm?"*

**Vấn đề:** Inverted Index truyền thống cần một máy chủ giữ toàn bộ bảng ánh xạ `keyword → [doc_id]`. Khi tập từ vựng lớn, đây chính là bottleneck duy nhất.

**Giải pháp:** Dùng **DHT (Distributed Hash Table)** để phân chia trách nhiệm. Mỗi từ khóa được hash → quyết định peer nào chịu trách nhiệm lưu posting list của từ khóa đó. Không node nào giữ toàn bộ index.

```
  hash("system")  = 42  →  Node 60 giữ posting list của "system"
  hash("database") = 137 →  Node 160 giữ posting list của "database"
  hash("network")  = 201 →  Node 210 giữ posting list của "network"
```

#### 🔴 Thách Thức 2 — Định Tuyến Hiệu Quả (Efficient Routing — O(log N))

> *"Làm thế nào tìm đúng peer giữ keyword mà không cần hỏi tất cả mọi người?"*

**Vấn đề:** Trong mạng P2P naive (flooding), để tìm một key phải broadcast tới tất cả node → `O(N)` tin nhắn, gây tắc nghẽn khi mạng lớn.

**Giải pháp:** **Chord DHT với Finger Table** — mỗi node lưu `m = 8` con trỏ shortcut tới các node theo bước nhảy cấp số nhân trên vòng ring. Mọi truy vấn được định tuyến trong `O(log N)` bước thay vì `O(N)`.

```
  Không flooding:   Peer 0 → Peer 1 → Peer 2 → ... → Peer N   (O(N) hops)
  Dùng Chord:       Peer 0 → Peer 4 → Peer 6 → Peer 7          (O(log N) hops)
```

#### 🔴 Thách Thức 3 — Chịu Lỗi Khi Node Rời Mạng (Churn Resilience)

> *"Làm thế nào để hệ thống không mất dữ liệu khi một peer đột ngột ngắt kết nối?"*

**Vấn đề:** Trong môi trường P2P thực tế, node có thể chết bất cứ lúc nào (mất điện, đứt mạng). Nếu node đang giữ posting list của một từ khóa quan trọng mà chết đột ngột → mất dữ liệu, truy vấn trả về rỗng.

**Giải pháp:** Mỗi node tự động gửi **1 bản sao (replica)** của dữ liệu sang successor trực tiếp ngay sau mỗi lần ghi. Kết hợp với **Stabilization Protocol**chạy định kỳ mỗi 5 giây để tự phục hồi topology khi ring thay đổi.

---

## 2.2 Các Thuật Toán Đã Sử Dụng

Hệ thống sử dụng **9 thuật toán** thuộc 4 nhóm chức năng:

---

### Nhóm 1 — DHT Core (Định Tuyến & Lưu Trữ)

#### 1. Consistent Hashing

Ánh xạ cả keyword và node ID lên cùng một không gian hash **vòng tròn**`[0, 255]` bằng hàm `SHA-1(key) % 256` (với `m = 8` bit).

**Ý nghĩa cốt lõi:** Khi node join hoặc leave, chỉ `1/N` phần dữ liệu cần di chuyển sang chủ mới — thay vì phải rehash toàn bộ như modulo thông thường. Đây là nền tảng để hệ thống scale mà không gây gián đoạn.

#### 2. Chord — Finger Table Routing

Mỗi node duy trì một **finger table gồm 8 con trỏ** (index 0 đến 7) trỏ đến các node theo công thức:

```
finger[i] = successor(node_id + 2^i) mod 2^m
```

Khi định tuyến, node nhảy vọt đến `finger[i]` lớn nhất mà vẫn nhỏ hơn key đích — tiến dần về đúng node theo cấp số nhân, đạt `O(log N)` hops.

*Ví dụ với m=8, node N10 tìm key=73:*

```
finger[0] = N11,  finger[1] = N12,  finger[2] = N14,
finger[3] = N18,  finger[4] = N26,  finger[5] = N42,
finger[6] = N74   ← nhảy thẳng đến N74 (gần key=73 nhất)
```

#### 3. Chord — Stabilization Protocol

Định kỳ mỗi **5 giây**, mỗi node tự động chạy 2 tác vụ:

- `stabilize()` → hỏi successor: *"predecessor của bạn là ai?"* → phát hiện node mới chen vào giữa → cập nhật successor/predecessor cho đúng.
- `fix_fingers()` → cập nhật lần lượt từng entry trong finger table bằng cách gọi `find_successor()` cho từng mốc `2^i`.

Cơ chế này đảm bảo ring luôn nhất quán dù không có thay đổi nào xảy ra, phòng ngừa finger table bị stale sau churn.

---

### Nhóm 2 — Text Processing (Xử Lý Văn Bản)

#### 4. Inverted Index Construction

Từ nội dung 100 truyện ngắn, xây dựng bảng ánh xạ ngược: `keyword → Set[doc_id]`.

Pipeline xử lý mỗi document:

```
raw_text → lowercase → tokenize → remove_stopwords → hash(keyword) → DHT.put()
```

Khi nhiều peer cùng publish một keyword, hệ thống dùng **union (không ghi đè**)để merge posting list — đảm bảo không mất dữ liệu.

#### 5. Tokenization & Stopword Removal

Chuẩn hóa văn bản trước khi indexing và querying:

```python
tokens = re.findall(r'\b[a-z]+\b', text.lower())
tokens = [t for t in tokens if t not in STOPWORDS]
```

Loại bỏ stopwords ("the", "a", "is"...) giúp giảm kích thước posting list cho các từ phổ biến không có giá trị phân biệt — trực tiếp giảm tải DHT.

---

### Nhóm 3 — Query Engine (Truy Vấn Phân Tán)

#### 6. Distributed AND Query với Incremental Intersection

Giải quyết truy vấn đa từ khóa trong môi trường phân tán theo luồng tuần tự:

```
Query: "system AND database"
  ↓ Parse → ["system", "database"]
  ↓ hash("system") → Chord routing → Node 60 → PostingList_A = {1, 5, 23}
  ↓ FinalSet = {1, 5, 23}
  ↓ hash("database") → Chord routing → Node 160 → PostingList_B = {1, 8, 23}
  ↓ FinalSet = FinalSet ∩ PostingList_B = {1, 23}
  ↓ Kết quả: [DocID 1, DocID 23]
```

#### 7. Early Stop Optimization

Nếu `FinalSet = ∅` tại bất kỳ bước intersection nào → dừng ngay, không fetch các keyword còn lại. Trong phép AND, tập rỗng nhân với bất kỳ tập nào vẫn cho tập rỗng → tiết kiệm `(n-1)` network round-trip không cần thiết.

---

### Nhóm 4 — Tracing & Recovery (Ghi Vết & Phục Hồi)

#### 8. In-band Reverse Accumulation Tracing

Ghi lại toàn bộ đường đi thực tế của mỗi truy vấn mà **không tốn thêm kết nối mạng mới**. Cơ chế hoạt động theo mô hình tích lũy ngược:

```
Initiator (N10) → FIND_SUCCESSOR → Node A (N40) → Node B (N60)
                                                    ↓ RESOLVED
                              ← path:[Hop_A, Hop_B] ↙
← path:[Hop_N10, Hop_A, Hop_B]
```

Mỗi node trung gian "ký tên" vào `response.data["path"]` khi trả ngược về, tạo thành trace đầy đủ và chính xác 100% tại Initiator.

#### 9. Churn Recovery — Replica Promotion & Re-replication

Cơ chế phục hồi 2 bước khi phát hiện node predecessor chết (qua heartbeat ping):

**Bước 1 — Promote:** Node hiện tại đưa toàn bộ `replica_store` lên làm `dht_store` chính (xem `_promote_replicas()`), giải quyết "không tìm thấy tài liệu" sau khi node chứa primary data ngừng hoạt động.

**Bước 2 — Re-replicate:** Sau khi promote, node gửi toàn bộ dữ liệu vừa thăng cấp sang successor mới qua `BULK_STORE_REPLICA` — đảm bảo luôn có ít nhất 1 bản sao dự phòng dù churn xảy ra liên tiếp.

---

### Tổng Kết — Bảng Thuật Toán

| \# | Thuật Toán | Nhóm | Vai Trò Chính |
| --- | --- | --- | --- |
| 1 | Consistent Hashing | DHT Core | Phân chia không gian key lên ring vòng tròn |
| 2 | Chord Finger Table | DHT Core | Định tuyến `O(log N)` với 8 con trỏ shortcut |
| 3 | Stabilization Protocol | DHT Core | Tự phục hồi topology ring mỗi 5 giây |
| 4 | Inverted Index Construction | Text Processing | Xây dựng bảng ánh xạ `keyword → Set[doc_id]` |
| 5 | Tokenization & Stopword Removal | Text Processing | Chuẩn hóa văn bản trước indexing/querying |
| 6 | Distributed AND Query | Query Engine | Truy vấn đa từ khóa phân tán, giao tập tuần tự |
| 7 | Early Stop Optimization | Query Engine | Dừng sớm khi intersection rỗng, tiết kiệm bandwidth |
| 8 | Reverse Accumulation Tracing | Tracing | Ghi vết đường đi routing chính xác, in-band |
| 9 | Churn Recovery | Recovery | Promote replica → re-replicate khi node chết |

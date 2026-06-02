# 3. Đặc Tả Dataset

---

## Source (Nguồn Dữ Liệu)

Dataset được sinh tổng hợp (synthetic) phục vụ riêng cho mục đích demo đề tài.

- **File:** [`p2p_library_100_stories.json`](file:///e:/LEARN/HTPT/p2p_library_100_stories.json)
- **Vị trí:** Thư mục gốc của project (`e:/LEARN/HTPT/`)
- **Lý do dùng synthetic:** Chủ động kiểm soát vocabulary size và term distribution
  → dễ viết test có kết quả xác định; không phụ thuộc vào nguồn dữ liệu bên ngoài.

---

## Size (Kích Thước)

| Thuộc tính | Giá trị |
|---|---|
| Tổng số tài liệu | **100 short stories** |
| Kích thước file | **~34 KB** (34,068 bytes) |
| Định dạng | JSON Array |
| Ngôn ngữ nội dung | Tiếng Anh |

---

## Schema (Cấu Trúc Dữ Liệu)

Mỗi document trong dataset có cấu trúc JSON gồm 4 trường:

```json
{
    "id":       1,
    "title":    "The P2P Voyager",
    "category": "Tech",
    "content":  "In a decentralized universe, every star acts as a peer node..."
}
```

| Trường | Kiểu | Vai Trò Trong Hệ Thống |
|---|---|---|
| `id` | `int` | Định danh tài liệu — dùng làm **DocID** trong posting list |
| `title` | `string` | Tiêu đề truyện — hiển thị kết quả tìm kiếm |
| `category` | `string` | Thể loại (Tech, Fantasy, Cyberpunk, Sci-Fi...) |
| `content` | `string` | Nội dung truyện — **nguồn chính để tokenize & build inverted index** |

> **Trường được sử dụng chủ yếu:** `id` và `content`.  
> `content` được tokenize để xây dựng inverted index; `id` làm khóa lưu trữ trong DHT.

---

## Fragmentation Strategy (Chiến Lược Phân Mảnh Dữ Liệu)

Hệ thống áp dụng **2 lớp phân mảnh độc lập**, đều dựa trên **Consistent Hashing**:

### Lớp 1 — Phân Mảnh Inverted Index (Keyword → DocIDs)

```
keyword  →  SHA-1(keyword) % 256  →  Node chịu trách nhiệm (Successor)
```

- Mỗi từ khóa được hash → xác định node nào giữ posting list của từ khóa đó.
- Không node nào giữ toàn bộ index; mỗi node chỉ quản lý khoảng hash thuộc mình.
- Khi nhiều peer cùng publish một keyword → **union (merge)** posting list, không ghi đè.

### Lớp 2 — Phân Mảnh Nội Dung Tài Liệu (DocID → Content)

```
doc_id  →  SHA-1(str(doc_id)) % 256  →  key_id
       →  Chord routing O(log N) qua finger table  →  target_node
       →  GET_CONTENT tới target_node  →  full JSON content
```

- Nội dung từng truyện được lưu tại node do hàm hash của `doc_id` chỉ định.
- Khi user muốn đọc nội dung một tài liệu, hệ thống **không query trực tiếp** mà phải
  thực hiện **Chord routing** (O(log N) hops qua finger table) để tìm ra node chịu
  trách nhiệm, sau đó mới gửi `GET_CONTENT` đến đúng node đó.
- Cả Lớp 1 (keyword) và Lớp 2 (content) đều đi qua cùng một cơ chế routing.

### Tham Số Cấu Hình

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `m` (bit space) | `8` | Không gian ring: `[0, 255]` |
| Hàm hash | `SHA-1(key) % 256` | Ánh xạ keyword/docID lên ring |
| Số nodes demo | `5 nodes` (port 8001–8005) | Node ID: 10, 60, 110, 160, 210 |
| Replication Factor | `1` | 1 bản sao lưu tại successor trực tiếp |
| Phân chia ban đầu | Round-robin theo node | 100 docs chia đều cho 5 nodes (20 docs/node) |

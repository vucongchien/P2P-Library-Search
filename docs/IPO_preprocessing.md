# Tài Liệu Thiết Kế IPO (Input - Process - Output)
**Module:** Tiền Xử Lý Dữ Liệu (Data Preprocessing)
**Dự án:** P2P Library Search (Mạng DHT Chord)

---

## 1. Đầu Vào (Input)

Quá trình tiền xử lý nhận đầu vào chủ yếu là kho dữ liệu thô (Raw Dataset) dưới định dạng JSON và một số tham số thiết lập (Configuration).

### 1.1 Dataset gốc
- **Tên file:** `p2p_library_100_stories.json`
- **Định dạng:** Danh sách rẽ nhánh (List) các đối tượng JSON (Dictionary).
- **Trường dữ liệu (Fields):** Mỗi object bao gồm các thành phần sau:
  - `id` (int): Định danh duy nhất cho tài liệu.
  - `title` (str): Tiêu đề của tài liệu.
  - `category` (str): Thể loại.
  - `content` (str): Nội dung chính của tài liệu.

### 1.2 Tham số thiết lập (Config)
- `num_peers` (int): Số lượng nút (peer) dự kiến trong mạng mô phỏng (Mặc định: 5). Tham số này quy định mức độ chia nhỏ (chunk) tài liệu cho mỗi cụm lưu trữ (local storage).
- `input_path` (str): Đường dẫn đến file dataset.
- `output_dir` (str): Thư mục nơi hệ thống sẽ ghi các file thành phẩm sau quá trình đóng gói.

---

## 2. Quá Trình Xử Lý (Process)

Bộ xử lý chia thành dòng chảy pipeline gồm 5 bước tuần tự, hoạt động tách biệt để dễ kiểm thử (Unit tests) và nâng cấp:

### Bước 1: Load & Validate (`loader.py`)
- Đọc file JSON từ `input_path`.
- Loại bỏ các document lỗi:
  - Bọc cấu trúc không phải chuỗi JSON chuẩn.
  - Thiếu field định danh `id` hoặc bị trùng lặp `id`.
  - Thiếu `content` hoặc nội dung rỗng.
- Tính toán thống kê lượt thành công/bỏ qua vào đối tượng `report`.

### Bước 2: Text Cleaning (`cleaner.py`)
- Nối chuỗi nội dung quan trọng: `text = title + " " + content`.
- Chuyển toàn bộ chuỗi ký tự về dạng chữ in thường (Lowercase).
- Thực hiện Regex (`[^a-z\s]`) để xóa toàn bộ dấu câu, số và các ký tự đặc biệt, chỉ giữ lại các chữ cái `a-z` và khoảng trắng.
- Cắt gọt và xóa các khoảng trống thừa.

### Bước 3: Tokenize & Normalize (`tokenizer.py`)
- Cắt (split) văn bản tĩnh thành mảng từ đơn (tokens).
- Loại bỏ stopword bằng cách đối chiếu với danh sách hơn 120+ standard english stopwords.
- Loại bỏ các token quá ngắn (nhỏ hơn 3 ký tự).
- Deduplicate: Biến collection các phần tử thành một danh sách kết quả duy nhất cho mỗi document, loại bỏ các từ lặp lại trong cùng 1 bài.
- *Lưu ý:* Không sử dụng Stemming hay Lemmatization, duy trì dạng nguyên thuỷ để Index và Query minh bạch.

### Bước 4: Index Building (`index_builder.py`)
- Build Global Index: Lặp qua toàn bộ Array của tokens và document ID tương ứng để sinh ra cấu trúc Dictionary ánh xạ chéo `Keyword` $\rightarrow$ `Set[DocIDs]`.
- Build Peer Local Index: Chia nhỏ Document theo chunk (`chunk_size = tổng docs / num_peers`). Áp dụng mô hình Build Global Index nhưng giới hạn trong cụm data mà Peer đó sở hữu. 

### Bước 5: Serialization (`pipeline.py`)
- Parse tập Inverted Index (từ kiểu `Set` sang dạng mảng `List` - do giới hạn của JSON formater).
- Kết xuất toàn bộ đối tượng In/Out ra dạng JSON file về thư mục `output_dir`.

---

## 3. Đầu Ra (Output)

Hệ thống kết xuất ra 4 file vật lý phục vụ mô phỏng phân tán DHT (Chord Routing) và truy xuất sau này. Các file được lưu trữ trong thư mục `output`.

### 3.1. `processed_docs.json`
Chứa thông tin sạch của các tài liệu. Sử dụng làm cơ sở dữ liệu (Storage) để truy vấn xuất Content khi mạng P2P lấy được `doc_id` của tài liệu.
```json
[
  {
    "id": 1,
    "title": "The P2P Voyager",
    "category": "Tech",
    "tokens": ["decentralized", "universe", "peer", "node", "voyager"],
    "raw_content": "In a decentralized universe, every star acts as a peer node."
  }
]
```

### 3.2. `inverted_index.json`
Đóng vai trò làm Ground Truth (Bảng tra cứu trung tâm dùng để Debug/Đối soát xem DHT có trả về đúng kết quả lý tưởng hay không).
```json
{
  "peer": [1, 5, 23],
  "universe": [1, 21, 23],
  "node": [1, 25, 40]
}
```

### 3.3. `peer_local_indexes.json`
Chứa các Index độc lập được chia cắt cho từng Peer riêng lẻ. Dữ liệu này đóng vai trò mồi (seed) để load lên bộ nhớ DHT của mỗi node mạng mô phỏng.
```json
{
  "peer_0": {
    "peer": [1, 5],
    "voyager": [1]
  },
  "peer_1": {
    "peer": [23]
  }
}
```

### 3.4. `preprocessing_report.json`
Báo cáo quá trình xử lý, giúp Data Engineer đánh giá chất lượng đầu vào của tập dữ liệu mới khi pipeline được chạy tái sử dụng.
```json
{
  "total_raw": 100,
  "total_valid": 100,
  "total_skipped": 0,
  "skip_reasons": [],
  "vocabulary_size": 250
}
```

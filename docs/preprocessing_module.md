# Tài liệu: Module Tiền Xử Lý Dữ Liệu (Preprocessing)

Tài liệu này mô tả chi tiết cách thức hoạt động của module tiền xử lý dữ liệu, đóng vai trò chuyển đổi dữ liệu gốc (100 short stories) thành định dạng **Inverted Index** tối ưu để phục vụ cho P2P Search Engine (Chord DHT).

---

## 1. Cấu trúc thư mục

Module được đặt gọn gàng trong thư mục `preprocessing/`, gồm các file sau:

- **`models.py`**: Định nghĩa cấu trúc dữ liệu (DataClasses). Giúp code tường minh và dễ bảo trì hơn. Bao gồm `ProcessedDoc` (tài liệu đã chuẩn hóa) và `PreprocessingReport` (báo cáo kết quả).
- **`pipeline.py`**: Trái tim của module. Chứa toàn bộ các hàm xử lý logic đi từ đọc file đến thao tác làm sạch văn bản, tạo index.
- **`main.py`**: File thực thi chính. Chỉ cần chạy file này, toàn bộ quy trình sẽ được kích hoạt.
- **`tests/`**: Thư mục chứa Unit Tests (Dùng mock data ảo, tránh chạy trên data thật rườm rà). Đảm bảo mọi logic đều chạy trơn tru trước khi áp dụng.

---

## 2. Quy trình 5 bước (5 Phases) hoạt động như thế nào?

Quá trình tiền xử lý đi qua 5 bước tuần tự, được thiết kế độc lập để dễ dàng bảo trì:

### Bước 1: Đọc & Xác thực dữ liệu (Load & Validate)
- Mở file gốc `p2p_library_100_stories.json`.
- Kiểm tra các bài viết (Document):
  - Bỏ qua các bài viết không có trường `content` hoặc nội dung bị rỗng.
  - Gắn nhãn **Cảnh báo (Warning)** nếu bài viết không có tiêu đề, hoặc bị trùng lặp mã ID.
  - Kết quả: Lọc lại được các tài liệu "Sạch" và hợp lệ.

### Bước 2: Trích xuất & Làm sạch văn bản (Cleaning)
- Ghép Tiêu đề (`title`) và Nội dung (`content`) lại với nhau thành một đoạn văn bản duy nhất để tăng độ chính xác khi tìm kiếm.
- Đưa tất cả văn bản về chữ thường (lowercase).
- **Làm sạch**: Xóa toàn bộ số, dấu câu và các ký tự đặc biệt. Chỉ giữ lại các chữ cái tiếng Anh từ `a` đến `z`.

### Bước 3: Tách từ (Tokenization)
- Tách đoạn văn thành từng từ riêng lẻ dựa vào khoảng trắng.
- **Tối ưu hóa**:
  - Bỏ đi các từ vô nghĩa (Stopwords) tự định nghĩa siêu nhẹ (như *the, a, is, in...*). Tái sử dụng code cực lẹ không cần tải bộ dữ liệu NLTK tốn thời gian.
  - Xóa luôn các từ quá ngắn (< 3 ký tự) vì người dùng ít khi tìm kiếm theo cấu trúc này.
  - Bỏ các từ bị lặp lại trong cùng một tài liệu (Deduplication) để giảm dung lượng mạng. (Inverted index chỉ quan tâm *tài liệu nào có chữ đó*, không quan tâm cấu trúc *xuất hiện mấy lần*).

### Bước 4: Tạo Inverted Index (Build Index)
Hệ thống sử dụng hai loại Inverted Index:
1. **Global Index** (Bảng tổng): Gom toàn bộ từ vựng và chỉ rõ từ nào đang nằm ở ID tài liệu nào.
2. **Per-Peer Local Index** (Bảng phân chia): Cắt 100 tài liệu chia ra làm 5 nhóm (5 peers) cho Network. Mỗi peer chỉ tự lập Inverted Index dựa trên phần dữ liệu của riêng nó. Đây là dữ liệu dùng để public lên mạng Chord DHT sau này.

### Bước 5: Lưu trữ (Serialize)
Toàn bộ kết quả được xuất ra định dạng JSON và lưu tại tập trung tại biến xuất `dataset/processed/`.
- `processed_docs.json`: Trữ toàn bộ file cấu trúc gọn gàng lấy tokens làm nền tảng.
- `inverted_index.json`: Từ khóa → Danh sách bài viết.
- `peer_local_indexes.json`: Danh mục Index theo nội dung từng Peer.
- `preprocessing_report.json`: Báo cáo thống kê của quá trình Indexing (Có bao nhiêu từ, xử lý thành công bao nhiêu tài liệu).

---

## 3. Cách chạy Module

Vì toàn bộ dự án đã được quản lý tập trung bằng  `uv` siêu tốc của Python, bạn không cần cài cắm gì quá phức tạp.

**Chạy Preprocessing và tạo Index (Khởi tạo kết quả):**
```powershell
uv run python -m preprocessing.main
```
> Kết quả tạo ra toàn bộ dữ liệu tại `dataset/processed/`

**Chạy toàn bộ Unit Tests (Cực nhanh để check lỗi):**
```powershell
uv run pytest preprocessing/tests/ -v
```

---

## 4. Tại sao lại lựa chọn thiết kế này?

1. Kịch bản **Hardcode Stopword** của Tiếng Anh được tuân thủ giúp tốc độ cài đặt environment gần như = 0ms. Hệ thống gọn lẹ và rất dễ triển khai lên bất cứ máy người dùng P2P nào.
2. Chặn các nguy cơ tiềm ẩn bằng hệ thống báo lỗi / Warning riêng, **không làm sập phần mềm** khi gặp 1 tài liệu lỗi (Ví dụ: Thiếu Content).
3. Đã sẵn sàng cho giai đoạn tiếp theo (Transport/DHT) cực mạnh mà không cần sửa tiếp phần Tiền xử lý dữ liệu nữa.

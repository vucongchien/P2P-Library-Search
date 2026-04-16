# Task: Tiền Xử Lí Dataset p2p_library_100_stories.json

## Mục tiêu tổng quát
Chuyển đổi raw JSON dataset (id, title, category, content) thành
**Inverted Index** sẵn sàng để publish lên Chord DHT.

Output cuối cùng: `keyword → Set[doc_id]`

---

## Sơ đồ Pipeline

```
[JSON file]
     │
     ▼
[PHASE 1] Load & Validate
     │  kiểm tra field, xử lý thiếu/null
     ▼
[PHASE 2] Text Extraction & Cleaning
     │  gộp title+content, xóa ký tự đặc biệt, lowercase
     ▼
[PHASE 3] Tokenize & Normalize
     │  tách từ, bỏ stopwords, (optional) stemming
     ▼
[PHASE 4] Build Inverted Index
     │  keyword → Set[doc_id]
     ▼
[PHASE 5] Serialize Output
        processed_docs.json + inverted_index.json
```

---

## PHASE 1 — Load & Validate

- `[ ]` **1.1 Load JSON**
  - Đọc file `p2p_library_100_stories.json`
  - Parse thành list of dict
  - Log: tổng số doc đọc được

- `[ ]` **1.2 Validate schema**
  - Kiểm tra mỗi doc có đủ 4 field: `id`, `title`, `category`, `content`
  - Kiểm tra `id` là unique (không trùng lặp)
  - Kiểm tra `content` không phải None/empty string
  - Log: số doc hợp lệ / số doc lỗi + lý do lỗi

- `[ ]` **1.3 Xử lý doc lỗi**
  - Nếu `content` rỗng/null → skip doc đó, log warning
  - Nếu `id` trùng → giữ cái đầu tiên, log warning
  - Nếu thiếu `title` → dùng empty string (không critical)

> **Tại sao**: Garbage in → garbage index. Validate sớm tránh lỗi âm thầm ở bước sau.  
> **Trade-off**: Skip doc lỗi thay vì raise exception → pipeline tiếp tục, không crash toàn bộ.

---

## PHASE 2 — Text Extraction & Cleaning

- `[ ]` **2.1 Quyết định field nào đưa vào index**
  - `content` → **bắt buộc** (nội dung chính)
  - `title` → **nên thêm** (từ khóa tiêu đề quan trọng)
  - `category` → **optional** (có thể dùng để filter sau)
  - Gộp: `text = title + " " + content`

- `[ ]` **2.2 Lowercase**
  - `text = text.lower()`
  - Lý do: "Database" = "database" = "DATABASE" về mặt semantic

- `[ ]` **2.3 Xóa ký tự đặc biệt**
  - Giữ lại: chữ cái a-z, khoảng trắng
  - Xóa: số, dấu câu, ký tự đặc biệt
  - Pattern: `re.sub(r'[^a-z\s]', ' ', text)`

- `[ ]` **2.4 Normalize whitespace**
  - Xóa tab, newline, multi-space
  - `re.sub(r'\s+', ' ', text).strip()`

> **Tại sao gộp title + content**: Người dùng hay search theo tiêu đề. Bỏ title → miss nhiều match quan trọng.  
> **Trade-off**: Xóa số → mất khả năng tìm "doc3" hay "chapter 5". OK cho dataset này vì short stories.

---

## PHASE 3 — Tokenize & Normalize

- `[ ]` **3.1 Tokenize (tách từ)**
  - Split by whitespace: `tokens = text.split()`
  - Hoặc dùng regex: `re.findall(r'\b[a-z]+\b', text)`

- `[ ]` **3.2 Bỏ Stopwords**
  - Dùng danh sách NLTK English stopwords hoặc hardcode set cơ bản
  - Các từ như: `the, a, an, is, are, was, were, in, on, at, to, of, and, or, not, it, he, she, they`
  - `tokens = [t for t in tokens if t not in STOPWORDS]`

- `[ ]` **3.3 Bỏ token quá ngắn**
  - Token < 3 ký tự thường không có nghĩa: "an", "to", "up"
  - `tokens = [t for t in tokens if len(t) >= 3]`

- `[ ]` **3.4 (Optional) Stemming**
  - Dùng Porter Stemmer nếu muốn "running" = "run" = "runs"
  - Cân nhắc: làm index nhỏ hơn nhưng mất chính xác từ gốc
  - **Khuyến nghị: KHÔNG stemming** để trace dễ đọc và debug

- `[ ]` **3.5 Deduplication per doc**
  - Một doc, mỗi keyword chỉ cần xuất hiện 1 lần trong index
  - `unique_tokens = list(set(tokens))`
  - Lý do: inverted index chỉ lưu membership, không phải frequency

> **Trade-off Stemming**:
> | | Có Stemming | Không Stemming |
> |---|---|---|
> | ✅ | Index nhỏ hơn, recall cao hơn | Từ gốc rõ ràng, dễ debug |
> | ❌ | Kết quả khó giải thích | "running" ≠ "run" khi search |
> 
> **Chọn không stemming** vì dataset này là demo học thuật, precision > recall.

---

## PHASE 4 — Build Inverted Index

- `[ ]` **4.1 Build global inverted index**
  ```
  inverted_index: Dict[str, Set[int]] = {}
  for doc in processed_docs:
      for token in doc.tokens:
          inverted_index[token].add(doc.id)
  ```

- `[ ]` **4.2 Thống kê sau khi build**
  - Tổng số unique keywords (vocabulary size)
  - Top 20 keywords phổ biến nhất (document frequency cao nhất)
  - Top 20 keywords hiếm nhất (df = 1)
  - Min/Max/Avg posting list size
  - Log tất cả để debug

- `[ ]` **4.3 Partition index theo peer**
  - Chia 100 docs thành N peer (N = 5 mặc định)
  - Peer i nhận docs `[i*20 : (i+1)*20]`
  - Mỗi peer chỉ build index từ tập doc của mình
  - Lưu: `peer_local_index[peer_id] = {keyword: set(doc_ids)}`

> **Tại sao lưu cả global lẫn local**: Global dùng để verify (ground truth), local là input thực sự cho DHT phase.

---

## PHASE 5 — Serialize Output

- `[ ]` **5.1 Lưu processed docs**
  ```json
  [
    {
      "id": 1,
      "title": "The P2P Voyager",
      "category": "Tech",
      "tokens": ["decentralized", "universe", "peer", "node", ...]
    },
    ...
  ]
  ```
  → File: `dataset/processed/processed_docs.json`

- `[ ]` **5.2 Lưu global inverted index**
  ```json
  {
    "distributed": [1, 5, 23, 47],
    "database": [1, 8, 23, 60],
    "peer": [1, 2, 3, 5, ...]
  }
  ```
  → File: `dataset/processed/inverted_index.json`

- `[ ]` **5.3 Lưu per-peer local index**
  ```json
  {
    "peer_0": {"decentralized": [1,5], "node": [1,2]},
    "peer_1": {"query": [20,25], "hash": [21,28]},
    ...
  }
  ```
  → File: `dataset/processed/peer_local_indexes.json`

- `[ ]` **5.4 Lưu preprocessing report**
  - Số doc processed, số token unique, thống kê stopword
  - → File: `dataset/processed/preprocessing_report.json`

---

## Unit Test Cần Viết

- `[ ]` `test_phase1_validate()` — doc thiếu field, id trùng, content rỗng
- `[ ]` `test_phase2_clean()` — uppercase → lower, ký tự đặc biệt bị xóa
- `[ ]` `test_phase3_tokenize()` — stopword bị bỏ, token ngắn bị bỏ
- `[ ]` `test_phase4_index()` — keyword có đúng doc_ids, không thiếu không thừa
- `[ ]` `test_phase4_partition()` — peer 0 chỉ có doc 0-19, không có doc 20+
- `[ ]` `test_phase5_serialize()` — file output đúng format, loadable lại được

---

## Output Files

```
e:\LEARN\HTPT\
└── dataset/
    ├── raw/
    │   └── p2p_library_100_stories.json   (input)
    └── processed/
        ├── processed_docs.json            (docs + tokens)
        ├── inverted_index.json            (global index)
        ├── peer_local_indexes.json        (per-peer index)
        └── preprocessing_report.json     (stats)
```

---

## Progress

- `[ ]` Phase 1: Load & Validate
- `[ ]` Phase 2: Text Cleaning
- `[ ]` Phase 3: Tokenize & Normalize
- `[ ]` Phase 4: Build Inverted Index
- `[ ]` Phase 5: Serialize Output
- `[ ]` Unit Tests

# Đề Tài 64 — Distributed Inverted Index: "P2P Library Search"
## Bản Phân Tích Thiết Kế & Lộ Trình Triển Khai


# V. Hiện Thực & Đánh Giá

## 5.1 Lộ Trình Triển Khai (7 Bước)

---

### 🔷 BƯỚC 0 — Thu Thập Dataset (Done)

**Làm gì**: Tải 100 short stories văn bản thuần túy.

**Nguồn dataset phù hợp:**
- Project Gutenberg (free, public domain)
- Script Python tự generate 100 doc synthetic

**Lý do chọn synthetic**: Chủ động control vocabulary size và term distribution → dễ viết test có kết quả xác định.

**Tradeoff**:
| | Real Dataset | Synthetic |
|---|---|---|
| ✅ | Thực tế hơn | Controllable, testable |
| ❌ | Khó predict kết quả test | Ít phong phú về ngôn ngữ |

**Kết quả**: `dataset/raw/doc_000.txt` → `doc_099.txt`

---

### 🔷 BƯỚC 1 — Text Preprocessing (Done)

**Làm gì:**
```python
def preprocess(text) → List[str]:
    text = text.lower()
    tokens = re.findall(r'\b[a-z]+\b', text)
    tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens
```

**Kiến thức cần**: Information Retrieval — Text Normalization, Stopword removal.

**Lý do bỏ stopwords**: "the", "a", "is" xuất hiện trong 99/100 tài liệu → posting list khổng lồ, không thêm giá trị phân biệt.

**Tradeoff**:
| | Giữ stopwords | Bỏ stopwords |
|---|---|---|
| ✅ | Phrase query chính xác hơn | Index nhỏ hơn, query nhanh |
| ❌ | DHT bị quá tải vì posting list lớn | Không query được "to be or not to be" |

**Test**: `test_preprocessing.py` — kiểm tra lowercase, stopword removal, special char.

---

### 🔷 BƯỚC 2 — Xây Dựng Chord DHT (Setup)



---

### 🔷 BƯỚC 3 — 



---

### 🔷 BƯỚC 4 — Query Engine & AND Resolution (Done)

**Làm gì**:
1. Parse query string → list of keywords
2. DHT lookup từng keyword → collect (posting_set, hop_path)
3. Intersect tất cả sets → final result
4. Ghi trace

**Kiến thức**: Set intersection trong distributed system, early termination optimization.

**Optimization quan trọng — Sort by smallest posting list first:**
```python
# Hỏi keyword ít phổ biến nhất trước → intersection nhỏ dần → ít work hơn
keywords.sort(key=lambda kw: estimated_df(kw))
```

**Tradeoff**:
| | Sequential | Parallel |
|---|---|---|
| ✅ | Trace rõ ràng, early termination | Nhanh hơn (latency) |
| ❌ | Chậm hơn nếu tất cả sets lớn | Trace phức tạp, hard to explain |

---

### 🔷 BƯỚC 5 — Metrics & Trace System 

**Làm gì**: Implement decorator/context manager để thu thập:
- `hops`: số lần route message
- `messages`: tổng số message trao đổi
- `latency`: time.time() delta (simulated)
- `trace`: ordered list of (from, to, action, keyword)

**Output format (JSON)**:
```json
{
  "query": "distributed AND database",
  "keywords": ["distributed", "database"],
  "steps": [
    {
      "keyword": "distributed",
      "path": [0, 3, 5],
      "hops": 2,
      "result_docs": [1, 5, 23]
    },
    {
      "keyword": "database",
      "path": [0, 2],
      "hops": 1,
      "result_docs": [1, 8, 23]
    }
  ],
  "final_result": [1, 23],
  "total_hops": 3,
  "total_messages": 5,
  "latency_ms": 12.3
}
```

---

### 🔷 BƯỚC 6 — Churn Simulation & Recovery

**Làm gì**: Simulate node failure:
```python
def simulate_churn(ring, leave_node_id):
    ring.remove_node(leave_node_id)      # Node leave
    ring.trigger_stabilize(rounds=3)    # Các node còn lại stabilize
    # Verify: query vẫn trả kết quả đúng (nhờ replication)
```

**Metrics thu thập**:
- Recovery time (số rounds stabilize cần thiết)
- Query success rate trước/sau churn

---

### 🔷 BƯỚC 7 — Visualization với NetworkX

**Làm gì**:
```python
import networkx as nx
import matplotlib.pyplot as plt

def draw_ring_topology(ring):
    G = nx.DiGraph()
    for node in ring.nodes:
        G.add_node(node.id)
        G.add_edge(node.id, node.successor.id, label="successor")
    nx.draw_circular(G, with_labels=True)

def draw_query_path(trace):
    # Highlight các edge được dùng trong query
    # Màu khác nhau cho từng keyword
```

---

## 5.2 Tech Stack & Lý Do Chọn

| Công cụ | Lý do |
|---|---|
| **Python 3.10+** | Dễ prototype, nhiều library |
| **hashlib.sha1** | Tính hash key cho DHT |
| **NetworkX** | Vẽ topology, highlight query path |
| **matplotlib** | Render graph |
| **pytest** | Unit test framework |
| **dataclasses** | Clean data model |

**Không dùng threading/asyncio thực sự**: Toàn bộ là **simulated** — peers là objects trong memory, message passing là function calls. Đây là cách standard để demo P2P algorithms mà không cần network setup.

## 5.3 Đánh Giá Theo Rubric

| Tiêu chí | Cách đáp ứng | Mục tiêu |
|---|---|---|
| **Routing Logic** | Chord finger table O(log N), multi-hop implemented | Excellent |
| **Churn Resilience** | Replication r=2, stabilize protocol | Excellent |
| **Analytical Metrics** | Hops, latency, message count per query | Excellent |
| **Implementation** | Message passing simulated, peer independence rõ ràng | Excellent |

## 5.4 Phân Tích Tradeoff Toàn Hệ Thống

### Simulated vs Real Network

**Chọn Simulated vì:**
- Không cần setup network infrastructure
- Reproducible results cho testing
- Dễ inject churn có kiểm soát
- Tập trung vào algorithm, không phải network engineering

**Đánh đổi**: Không có real latency, không có real packet loss — nhưng hoàn toàn phù hợp với scope của đề tài.

### DHT Replication vs No Replication

**Chọn r=2 vì:**
- Một node chết → vẫn có backup
- Không quá phức tạp để implement

**Đánh đổi**: Write traffic tăng gấp đôi khi publish, nhưng read vẫn O(1) từ primary.

### Chord Ring Size (m bit)

**Chọn m=8 (256 slots) vì:**
- Đủ lớn cho 5-20 peers
- Không bị collision với xác suất cao

**Đánh đổi**: m=4 (16 slots) đủ cho demo nhỏ nhưng finger table ít → routing kém hơn.

---

## 5.5 Thứ Tự Triển Khai Được Khuyến Nghị

```
Tuần 1:
  [x] Bước 0: Dataset (1 ngày)
  [x] Bước 1: Preprocessing (0.5 ngày)
  [x] Bước 2: Chord DHT + unit test (2 ngày)  ← core

Tuần 2:
  [ ] Bước 3: Index Build + unit test (1 ngày)
  [ ] Bước 4: Query Engine + test (1 ngày)
  [ ] Bước 5: Metrics & Trace (1 ngày)

Tuần 3:
  [ ] Bước 6: Churn simulation (1 ngày)
  [ ] Bước 7: Visualization (1 ngày)
  [ ] Bước 8: Demo & Report (1 ngày)
```

> **Critical Path**: Bước 2 (Chord DHT) là nền tảng. Tất cả bước còn lại phụ thuộc vào đây. Ưu tiên test kỹ bước này trước.

---

## 5.6 Kiến Thức Cần Nắm Vững

1. **Consistent Hashing**: tại sao hash(key) % N không đủ tốt khi N thay đổi.
2. **Chord Finger Table**: cách tính `finger[i] = successor(n + 2^i)`.
3. **Stabilization**: vì sao cần periodic stabilize sau khi node join/leave.
4. **Inverted Index**: forward vs inverted, posting list, merge operations.
5. **Set Intersection**: early termination khi một set rỗng.
6. **CAP Theorem**: hệ thống này hy sinh **Consistency** (stale reads ngay sau churn) để đổi lấy **Availability + Partition Tolerance**.

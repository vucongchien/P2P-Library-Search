# Đề Tài 64 — Distributed Inverted Index: "P2P Library Search"
## Bản Phân Tích Thiết Kế & Lộ Trình Triển Khai

---

# I. Giới Thiệu Đề Tài

## 1.1 Bối Cảnh & Động Lực

Các search engine truyền thống (Google, Elasticsearch) hoạt động theo mô hình **centralized**: một server trung tâm lưu toàn bộ index và phục vụ mọi truy vấn. Mô hình này có một số vấn đề cơ bản:
- **Single point of failure**: server trung tâm chết → toàn bộ hệ thống chết.
- **Bottleneck về tài nguyên**: khi dữ liệu scale, chi phí server tăng theo tuyến tính.
- **Không có data sovereignty**: tất cả tài liệu phải giao cho một thực thể duy nhất kiểm soát.

**P2P Library Search** giải quyết vấn đề này bằng cách phân tán cả dữ liệu và logic tìm kiếm ra nhiều **peer** ngang hàng — không có master/coordinator — mỗi peer chỉ biết một phần nhỏ của mạng.

## 1.2 Mục Tiêu Cụ Thể

| Mục tiêu | Mô tả |
|---|---|
| Distributed Indexing | Mỗi peer tự index một tập con 100 tài liệu |
| DHT-based Storage | Keyword → DocID mapping lưu trong Chord DHT |
| AND Query Resolution | Truy vấn đa từ khóa với giao tập kết quả |
| Query Trace | Bản ghi rõ ràng: peer nào được contact, theo thứ tự nào |
| Churn Handling | Hệ thống tiếp tục hoạt động khi một số peer rời |
| Metrics | Đo được: Hops, Latency, Message Overhead |

---

# II. Cơ Sở Khoa Học

## 2.1 Inverted Index — Khái Niệm Nền Tảng

**Inverted Index** là cấu trúc dữ liệu cốt lõi của mọi search engine.

```
Forward Index:   DocID → [word1, word2, ...]
Inverted Index:  word  → [DocID1, DocID2, ...]   ← ngược lại
```

**Tại sao dùng Inverted Index?**
- Truy vấn từ khóa cực nhanh: O(1) lookup thay vì scan toàn bộ tài liệu.
- Hỗ trợ tự nhiên phép AND/OR/NOT qua set intersection/union.
- Đây là nền tảng của Elasticsearch, Lucene, Solr.

**Ví dụ:**
```
doc1 = "distributed database"
doc2 = "distributed system"
doc3 = "relational database"

Inverted Index:
  "distributed" → {doc1, doc2}
  "database"    → {doc1, doc3}
  "system"      → {doc2}

Query: "distributed" AND "database":
  {doc1, doc2} ∩ {doc1, doc3} = {doc1}  ✅
```

## 2.2 Distributed Hash Table (DHT) — Chord Protocol

### Vấn đề DHT giải quyết
Khi có nhiều peer, làm sao biết **ai đang lưu** keyword nào? Không có server trung tâm để hỏi.

**DHT** là cơ chế phân tán key-value store mà **không có coordinator** — mỗi peer tự biết mình chịu trách nhiệm cho range key nào.

### Chord DHT — Lý Thuyết

Chord là thuật toán DHT phổ biến nhất, hoạt động trên **vòng tròn hash (ring)**:

```
Không gian key: 0 → 2^m - 1  (m-bit identifier space)
                  ┌─────────┐
              0 ──┤  Peer A ├── 25
                  └────┬────┘
                       │  vòng tròn
              200 ──┐  │  ┌─── 50
                ┌───┤  │  ├───┐
                │   │  ▼  │   │
          Peer D│  Chord Ring  │Peer B
                │             │
                └─────────────┘
                      │
                    100
                  Peer C
```

**Quy tắc phân công**: Mỗi key `k` được lưu tại peer có ID nhỏ nhất **≥ k** (gọi là `successor(k)`).

**Ví dụ với m=8 (256 node ID):**
```
Peers: A(id=10), B(id=60), C(id=110), D(id=200)

hash("distributed") = 45 → lưu tại B(60) vì 60 ≥ 45
hash("database")    = 95 → lưu tại C(110) vì 110 ≥ 95
hash("system")      = 15 → lưu tại B(60) vì 60 ≥ 15
```

### Finger Table — Routing Hiệu Quả O(log N)

Mỗi peer không biết tất cả peer khác. Nó chỉ biết **m entries** trong bảng định tuyến (finger table):

```
Peer A (id=10), m=3 (8 nodes):
  finger[0] = successor(10 + 2^0) = successor(11) = B(60)
  finger[1] = successor(10 + 2^1) = successor(12) = B(60)
  finger[2] = successor(10 + 2^2) = successor(14) = B(60)
```

**Routing**: khi cần tìm key `k`, peer chuyển tiếp request đến finger entry **lớn nhất mà vẫn nhỏ hơn k** → converge trong O(log N) hops.

## 2.3 P2P Architecture — So Sánh Các Mô Hình

| Đặc điểm | Centralized | Flooding | Chord DHT |
|---|---|---|---|
| Điểm lỗi đơn | Có (server) | Không | Không |
| Routing | O(1) | O(N) messages | O(log N) hops |
| Biết topology | Server biết hết | Không ai biết | Biết O(log N) neighbor |
| Scale | Kém | Kém | Tốt |
| Ví dụ thực tế | Traditional DB | Gnutella 0.4 | BitTorrent, Kademlia |

**Lý do chọn Chord DHT**: cân bằng giữa đơn giản (để implement) và đúng về học thuật (O(log N) routing, no SPOF).

## 2.4 AND Query trong Distributed Setting

Truy vấn `"A" AND "B"` trong hệ thống phân tán phức tạp hơn vì:
1. Keyword `"A"` có thể lưu ở Peer X
2. Keyword `"B"` có thể lưu ở Peer Y
3. Cần giao `set(A) ∩ set(B)` — nhưng hai set này ở hai nơi khác nhau

**Hai chiến lược:**
- **Sequential**: Hỏi X lấy set(A), sau đó hỏi Y lấy set(B), coordinator tính giao.
- **Parallel**: Hỏi X và Y đồng thời, gom kết quả về coordinator để tính giao.

Ta sẽ dùng **Sequential** (đơn giản, dễ trace) và có thể mở rộng song song.

---

# III. Phân Tích Hệ Thống

## 3.1 Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────┐
│                   CHORD DHT RING                    │
│                                                     │
│  ┌─────────┐    finger    ┌─────────┐               │
│  │ Peer 0  │─────────────▶│ Peer 3  │               │
│  │ docs:   │◀─────────────│ docs:   │               │
│  │ 0..19   │              │ 60..79  │               │
│  │ idx:    │              │ idx:    │               │
│  │{kw→doc} │              │{kw→doc} │               │
│  └────┬────┘              └────┬────┘               │
│       │    DHT Lookup          │                    │
│  ┌────▼────┐              ┌────▼────┐               │
│  │ Peer 1  │              │ Peer 4  │               │
│  │ docs:   │              │ docs:   │               │
│  │ 20..39  │              │ 80..99  │               │
│  └─────────┘              └─────────┘               │
│                                                     │
│  ┌─────────┐              ┌─────────┐               │
│  │ Peer 2  │              │ Peer 5  │               │
│  │ docs:   │              │ (spare) │               │
│  │ 40..59  │              │         │               │
│  └─────────┘              └─────────┘               │
└─────────────────────────────────────────────────────┘

Initiator Peer → DHT Lookup("distributed") → Peer X → [doc1, doc2]
              → DHT Lookup("database")    → Peer Y → [doc1, doc3]
              → Intersection             → [doc1]
```

## 3.2 Phân Rã Chức Năng

### Module 1: Dataset & Preprocessing
- **Input**: 100 raw text documents
- **Output**: cleaned tokenized documents với term frequency
- **Kỹ thuật**: lowercase, tokenize, loại stopwords

### Module 2: Chord DHT Engine
- Quản lý ring topology
- Finger table routing
- Successor/predecessor lookup
- Node join/leave (churn)

### Module 3: Distributed Indexer
- Mỗi peer nhận tập con documents
- Build local inverted index
- Publish entries vào DHT: `hash(keyword)` → lưu tại `successor(hash(keyword))`

### Module 4: Query Processor
- Parse AND query
- DHT lookup từng keyword
- Giao tập kết quả

### Module 5: Trace & Metrics Collector
- Đếm hops
- Đo message overhead
- Ghi trace path
- Visualize với NetworkX

## 3.3 Data Flow — Dòng Chảy Dữ Liệu

```
[100 text files]
      │
      ▼
[Preprocessor]
  lowercase + tokenize + remove stopwords
      │
      ▼
[Partition]
  doc 0-19  → Peer0
  doc 20-39 → Peer1
  ...
      │
      ▼  (mỗi peer chạy song song)
[Local Index Build]
  Peer0: {"once": [0,5,12], "upon": [0,1], ...}
      │
      ▼
[DHT Publish]
  hash("once") = 73 → successor(73) = Peer3
  PUT("once", [0,5,12]) vào Peer3
      │
      ▼
[Query Phase]
  User: "distributed AND database"
  → DHT GET("distributed") → hops: P0→P2→P3 → returns [doc_ids]
  → DHT GET("database")    → hops: P0→P1→P4 → returns [doc_ids]
  → INTERSECT → final result
      │
      ▼
[Trace Output]
  Query: "distributed AND database"
  Step 1: P0 → P2 (hop 1) → P3 returns {doc1, doc2}
  Step 2: P0 → P4 (hop 1) returns {doc1, doc3}
  Result: {doc1}
  Total hops: 3, Messages: 4
```

## 3.4 Xác Định Bottleneck & Điểm Rủi Ro

| Rủi ro | Mức độ | Xử lý |
|---|---|---|
| Node leave → mất key | Cao | Replication mỗi key sang successor + 1 |
| Hash collision | Thấp | m=8 bit→256 slots, đủ cho 5-10 peer |
| Query initiator chết giữa chừng | Trung bình | Timeout + retry |
| Finger table stale sau churn | Cao | Periodic stabilize() protocol |

---

# IV. Thiết Kế Phần Mềm

## 4.1 Cấu Trúc Thư Mục

```
p2p_library_search/
├── dataset/
│   ├── raw/                    # 100 file .txt
│   └── processed/              # sau tokenize
├── src/
│   ├── preprocessing.py        # text cleaning
│   ├── chord_node.py           # một peer trong ring
│   ├── chord_ring.py           # quản lý toàn bộ ring
│   ├── indexer.py              # build & publish inverted index
│   ├── query_engine.py         # AND query resolution
│   ├── metrics.py              # đo hops, latency, messages
│   └── visualizer.py           # NetworkX graph + trace
├── tests/
│   ├── test_chord.py
│   ├── test_indexer.py
│   ├── test_query.py
│   └── README.md               # mục lục test
├── demo/
│   └── demo_trace.py           # demo end-to-end
├── results/
│   ├── query_traces/           # json trace files
│   └── graphs/                 # png topology images
└── requirements.txt
```

## 4.2 Thiết Kế Class

### `ChordNode`
```python
class ChordNode:
    id: int                      # hash ID trong ring [0, 2^m)
    m: int                       # bit size
    fingers: List[ChordNode]     # finger table, size m
    predecessor: ChordNode
    local_store: Dict[str, Set[int]]  # keyword → {doc_ids}

    def find_successor(key_id) → ChordNode    # O(log N) routing
    def find_predecessor(key_id) → ChordNode
    def put(keyword, doc_ids)                 # lưu vào đúng node
    def get(keyword) → Set[int]               # lấy từ đúng node
    def join(known_node)                      # gia nhập ring
    def stabilize()                           # fix pointers
    def fix_fingers()                         # cập nhật finger table
    def notify(node)                          # báo predecessor
```

### `QueryEngine`
```python
class QueryEngine:
    ring: ChordRing
    trace_log: List[TraceEvent]

    def query_and(keywords: List[str]) → QueryResult
    def _lookup_keyword(kw) → Tuple[Set[int], List[HopEvent]]
    def _intersect(sets) → Set[int]
```

### `Metrics`
```python
@dataclass
class QueryResult:
    query: str
    result_doc_ids: Set[int]
    total_hops: int
    total_messages: int
    latency_ms: float
    trace: List[TraceEvent]

@dataclass
class TraceEvent:
    step: int
    from_peer: int
    to_peer: int
    action: str           # "ROUTE", "HIT", "RETURN"
    keyword: str
    timestamp: float
```

## 4.3 Chord Routing — Pseudo Code

```python
def find_successor(id):
    if id in (self.id, successor.id]:
        return successor
    else:
        n_prime = closest_preceding_node(id)
        return n_prime.find_successor(id)   # recursive / hop

def closest_preceding_node(id):
    for i in range(m-1, -1, -1):
        if fingers[i].id ∈ (self.id, id):
            return fingers[i]
    return self
```

## 4.4 DHT Publish Strategy (Index Build)

```python
def publish_index(peer, local_index):
    for keyword, doc_ids in local_index.items():
        key_id = sha1(keyword) % (2**m)
        target_peer = ring.find_successor(key_id)
        target_peer.merge_put(keyword, doc_ids)
        # merge_put: nếu key đã tồn tại → union set, không ghi đè
```

> **Tại sao merge_put?** Nhiều peer có thể index cùng keyword, cần gộp tất cả doc_ids lại.

## 4.5 AND Query Protocol

```
SEQUENTIAL (dễ trace):
  result_sets = []
  for kw in keywords:
    peer_path, doc_set = DHT.lookup(kw)  # trace path
    result_sets.append((kw, doc_set, peer_path))
  
  final = result_sets[0].doc_set
  for (kw, doc_set, path) in result_sets[1:]:
    final = final ∩ doc_set   # early termination nếu rỗng

Output trace:
  "Step 1: lookup('distributed'): P0→P3 (2 hops) → docs={1,5,23}"
  "Step 2: lookup('database'):    P0→P1→P4 (3 hops) → docs={1,8,23}"
  "Intersection: {1,23}"
  "Total: 5 hops, 6 messages"
```

## 4.6 Churn Resilience Design

**Vấn đề**: Peer B leave → các key lưu tại B mất.

**Giải pháp: Replication Factor r=2**
```
PUT(keyword, doc_ids):
  node1 = find_successor(hash(keyword))
  node2 = node1.successor          # replica
  node1.store(keyword, doc_ids)
  node2.store(keyword, doc_ids)   # backup
```

**Stabilization Protocol** (chạy mỗi T giây):
```python
def stabilize():
    x = self.successor.predecessor
    if x ∈ (self.id, self.successor.id):
        self.successor = x
    self.successor.notify(self)

def fix_fingers():
    self.next = (self.next + 1) % m
    self.fingers[self.next] = find_successor(self.id + 2**self.next)
```

---

# V. Hiện Thực & Đánh Giá

## 5.1 Lộ Trình Triển Khai (7 Bước)

---

### 🔷 BƯỚC 0 — Thu Thập Dataset

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

### 🔷 BƯỚC 1 — Text Preprocessing

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

### 🔷 BƯỚC 2 — Xây Dựng Chord DHT

**Làm gì**: Hiện thực `ChordNode` với:
- `join()`: gia nhập ring
- `find_successor()`: routing O(log N)
- `stabilize()` + `fix_fingers()`: maintain consistency
- `put()` / `get()`: key-value operations

**Kiến thức cần**: Chord paper (Stoica et al. 2001) — consistent hashing, finger table lookup.

**Tại sao Chord (không phải Kademlia/Pastry)?**
- Chord là đơn giản nhất về mặt lý thuyết.
- Rất nhiều pseudocode reference.
- Đủ để đạt mức "Excellent" theo rubric.

**Tradeoff**:
| | Chord | Kademlia |
|---|---|---|
| ✅ | Lý thuyết rõ, code đơn giản | XOR metric, hội tụ nhanh hơn |
| ❌ | Routing unidirectional, chậm hơn | Phức tạp hơn để implement |

**Test**: `test_chord.py`:
```python
def test_routing():
    # 5 nodes, m=8
    # PUT key=45, expect at successor(45)
    # GET key=45 from any node, verify correct node returns value

def test_churn():
    # Remove node, verify GET still works via replica
    # Verify stabilize() fixes successors
```

---

### 🔷 BƯỚC 3 — Distributed Index Build

**Làm gì**:
1. Chia 100 docs → 5 peer (mỗi peer 20 docs)
2. Mỗi peer build local inverted index
3. Mỗi peer publish entries vào DHT với `merge_put`

**Kiến thức**: Distributed indexing pipeline — map phase (local index) → shuffle phase (DHT routing).

**Tại sao mỗi peer publish vào DHT thay vì giữ local?**
- Nếu giữ local: query phải hỏi tất cả peers (O(N) messages) → không scale.
- Nếu publish vào DHT: query chỉ cần hỏi đúng 1 node (O(log N) hops).

**Tradeoff**:
| | Local Index chỉ | Publish vào DHT |
|---|---|---|
| ✅ | Không cần routing, đơn giản | Scale tốt, query nhanh |
| ❌ | OR-flooding, N messages | Index build tốn thêm DHT traffic |

**Test**: `test_indexer.py`:
```python
def test_index_build():
    ring = build_ring(5)
    index_docs(ring, docs)
    # verify "distributed" → exists in DHT at correct node
    # verify doc_ids set is correct union of all peers' contributions
```

---

### 🔷 BƯỚC 4 — Query Engine & AND Resolution

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

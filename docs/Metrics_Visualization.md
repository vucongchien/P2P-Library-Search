# Kế Hoạch: Metrics & Thống Kê / Visualizer Mạng

## Bối Cảnh & Phân Tích Hiện Trạng

### Codebase hiện tại đã có gì?

| Module | Trạng thái | Dữ liệu cung cấp |
|---|---|---|
| `transport.py` | ✅ Hoàn thiện | `message_log: List[Dict]` — mỗi entry `{"to": node_id, "message": Message}` |
| `models/query.py` | ✅ Hoàn thiện | `QueryResult`, `KeywordLookup`, `HopEvent` — trace chi tiết mỗi query |
| `query_engine.py` | ✅ Hoàn thiện | Đã tích hợp tracing, early stop, partial data flags |
| `chord/ring.py` | ✅ Hoàn thiện | `nodes: Dict`, `transport`, `stabilize_all()`, `remove_node()` |
| `chord/node.py` | ✅ Hoàn thiện | `finger_table`, `successor_id`, `predecessor_id`, `dht_store`, `replica_store` |
| `metrics.py` | ❌ Chưa có | — |
| `visualizer.py` | ❌ Chưa có | — |

### Nguồn dữ liệu sẵn có (Zero-Instrumentation)

Theo đúng triết lý PRD: **"Metrics đọc từ transport.message_log (không instrument Chord)"**.

```
transport.message_log = [
    {"to": 60, "message": Message(type="FIND_SUCCESSOR", sender_id=10, payload={"key": 73}, ttl=20)},
    {"to": 110, "message": Message(type="GET", sender_id=10, payload={"keyword": "system"})},
    {"to": 60, "message": Message(type="PUT", sender_id=10, payload={"keyword": "abc", "doc_ids": [1,2]})},
    ...
]
```

Mỗi `Message` chứa: `type`, `sender_id`, `payload`, `ttl`. Từ đây ta suy ra mọi thứ cần đo.

---

## Thiết Kế Chi Tiết

### 1. `metrics.py` — MetricsCollector

#### Mục tiêu
Đo lường hiệu năng hệ thống P2P **hoàn toàn thụ động** — chỉ đọc `transport.message_log` và `QueryResult`. Không sửa bất kỳ module nào khác.

#### Kiến trúc

```
┌────────────────────────────────────────────────┐
│               MetricsCollector                 │
│                                                │
│  Input:                                        │
│    - transport.message_log (passive read)      │
│    - List[QueryResult]   (optional, từ query)  │
│                                                │
│  Output:                                       │
│    - BatchMetrics (dataclass, serializable)     │
│                                                │
│  Phương thức:                                  │
│    ├── total_messages() → int                  │
│    ├── messages_by_type() → Dict[str, int]     │
│    ├── bandwidth_by_node() → Dict[int, dict]   │
│    ├── analyze_query(QueryResult) → QueryStats │
│    ├── generate_report() → BatchMetrics        │
│    └── compare(before, after) → ChurnDelta     │
└────────────────────────────────────────────────┘
```

#### Dataclasses đầu ra

```python
@dataclass
class QueryStats:
    """Thống kê chi tiết cho 1 query."""
    query: str
    total_hops: int
    total_messages: int
    avg_hops_per_keyword: float
    keywords_count: int
    result_count: int
    early_stopped: bool

@dataclass
class NodeTraffic:
    """Lưu lượng mạng của 1 node."""
    node_id: int
    sent: int         # số message gửi đi
    received: int     # số message nhận
    by_type_sent: Dict[str, int]
    by_type_received: Dict[str, int]

@dataclass
class BatchMetrics:
    """Báo cáo tổng hợp toàn hệ thống."""
    total_messages: int
    messages_by_type: Dict[str, int]
    node_traffic: List[NodeTraffic]
    
    # Query performance (nếu có query results)
    query_stats: List[QueryStats]
    avg_hops_per_query: float
    avg_messages_per_query: float
    
    # DHT health
    total_keys_in_dht: int
    keys_distribution: Dict[int, int]   # node_id → số key
    replication_coverage: float          # % keys có replica

@dataclass
class ChurnDelta:
    """So sánh metrics trước/sau churn."""
    before: BatchMetrics
    after: BatchMetrics
    messages_delta: int
    avg_hops_delta: float
    keys_lost: int
    keys_recovered_from_replica: int
    query_results_match: bool          # kết quả query có đồng nhất?
```

#### Logic phân tích message_log

| Chỉ số | Cách tính từ message_log |
|---|---|
| **Total messages** | `len(message_log)` |
| **By type** | Group by `msg.type` → Counter |
| **Sent per node** | Group by `msg.sender_id` → Counter |
| **Received per node** | Group by `log["to"]` → Counter |
| **Routing hops** | Đếm entries có `type == "FIND_SUCCESSOR"` |
| **DHT operations** | Đếm `PUT`, `GET`, `STORE_REPLICA` |
| **Stabilization cost** | Đếm `NOTIFY`, `GET_PREDECESSOR`, `PING` |

#### Snapshot & Compare cho Churn

```python
class MetricsCollector:
    def snapshot(self) -> BatchMetrics:
        """Chụp trạng thái hiện tại."""
        
    def compare(self, before: BatchMetrics, after: BatchMetrics) -> ChurnDelta:
        """So sánh 2 snapshot trước/sau sự kiện churn."""
```

---

### 2. `visualizer.py` — NetworkVisualizer

#### Mục tiêu
Vẽ biểu đồ Chord ring topology bằng NetworkX + matplotlib, highlight đường đi query.

#### Kiến trúc

```
┌──────────────────────────────────────────────────┐
│              NetworkVisualizer                    │
│                                                  │
│  Input:                                          │
│    - ChordRing (đọc nodes, finger_table, etc.)   │
│    - QueryResult (optional, vẽ query path)       │
│                                                  │
│  Output:                                         │
│    - PNG files lưu vào results/graphs/            │
│                                                  │
│  Phương thức:                                    │
│    ├── draw_ring_topology(save_path)             │
│    ├── draw_finger_tables(save_path)             │
│    ├── draw_query_path(QueryResult, save_path)   │
│    ├── draw_dht_distribution(save_path)          │
│    └── draw_churn_comparison(before, after)      │
└──────────────────────────────────────────────────┘
```

#### Chi tiết từng hàm vẽ

##### `draw_ring_topology()`
- **Layout**: Vòng tròn (circular layout)
- **Nodes**: Hiển thị peer ID, số docs, số DHT keys
- **Edges xanh lá**: successor pointer (vòng chính)  
- **Edges xám nhạt**: finger table entries (shortcut)
- **Label**: Node ID ở giữa, metadata ở ngoài

##### `draw_query_path(query_result)`
- Vẽ topology cơ bản + overlay đường đi routing
- Mỗi keyword lookup → 1 màu khác nhau
- Mũi tên chỉ hướng routing
- Legend: keyword → color mapping
- Node khởi tạo (initiator) có viền đặc biệt
- Node đích (responsible_peer) có màu highlight

##### `draw_dht_distribution()`
- Bar chart: số keys mỗi node giữ
- Stacked: dht_store vs replica_store
- Giúp đánh giá load balancing

##### `draw_churn_comparison(before_ring, after_ring)`
- 2 subplot cạnh nhau: trước/sau churn
- Highlight node đã bị xóa (màu đỏ, gạch chéo)
- Highlight các pointer đã thay đổi

---

## Trade-offs

| Quyết định | Chọn | Bỏ | Lý do |
|---|---|---|---|
| Nguồn dữ liệu metrics | **Passive read từ message_log** | Instrument Chord code | Zero coupling — không sửa core DHT logic |
| Thư viện vẽ | **NetworkX + matplotlib** | Plotly, D3.js | Offline-friendly, xuất PNG trực tiếp, đủ cho báo cáo |
| Snapshot cho churn comparison | **Serialize BatchMetrics** | Re-compute từ log | Nhanh hơn, tránh re-parse toàn bộ log |
| Ring layout | **Circular layout cố định** | Spring/force layout | Trực quan đúng bản chất Chord ring |
| message_log format | **Giữ nguyên, bổ sung `timestamp` optional** | Thay đổi format | Backward-compatible |

> [!IMPORTANT]
> **Cần bổ sung `sender_id` tracking**: message_log hiện chỉ ghi `{"to": node_id, "message": msg}`. Để tính "received per node" chính xác, ta dùng `message.sender_id` (đã có sẵn trong Message object). **Không cần sửa transport.py**.

---

## Proposed Changes

### Dependencies

#### [MODIFY] [pyproject.toml](file:///e:/LEARN/HTPT/p2p_search/pyproject.toml)
- Thêm `networkx` và `matplotlib` vào dependencies

---

### Metrics Module

#### [NEW] [metrics.py](file:///e:/LEARN/HTPT/p2p_search/src/metrics.py)
- Class `MetricsCollector`: đọc `transport.message_log` + `ChordRing` state
- Dataclasses: `QueryStats`, `NodeTraffic`, `BatchMetrics`, `ChurnDelta`
- Methods: `total_messages()`, `messages_by_type()`, `bandwidth_by_node()`, `analyze_query()`, `generate_report()`, `snapshot()`, `compare()`
- Export `to_dict()` cho mọi dataclass → JSON serializable

---

### Visualizer Module

#### [NEW] [visualizer.py](file:///e:/LEARN/HTPT/p2p_search/src/visualizer.py)
- Class `NetworkVisualizer`: nhận `ChordRing` + optional `QueryResult`
- Methods: `draw_ring_topology()`, `draw_finger_tables()`, `draw_query_path()`, `draw_dht_distribution()`, `draw_churn_comparison()`
- Output: PNG files vào `results/graphs/`

---

### Tests

#### [NEW] [test_metrics.py](file:///e:/LEARN/HTPT/p2p_search/tests/test_metrics.py)
- Test `total_messages` đếm đúng
- Test `messages_by_type` phân loại chính xác
- Test `bandwidth_by_node` tính sent/received đúng
- Test `analyze_query` từ QueryResult mẫu
- Test `generate_report` tổng hợp đúng
- Test `snapshot` + `compare` cho churn delta
- Test edge cases: empty log, single node, no queries

#### [NEW] [test_visualizer.py](file:///e:/LEARN/HTPT/p2p_search/tests/test_visualizer.py)
- Test khởi tạo visualizer với ring hợp lệ
- Test `draw_ring_topology` tạo file PNG
- Test `draw_query_path` với QueryResult mẫu
- Test `draw_dht_distribution` xuất chart
- Test edge cases: ring 1 node, ring sau churn

#### [NEW] [tests/README_metrics_visualizer.md](file:///e:/LEARN/HTPT/p2p_search/tests/README_metrics_visualizer.md)
- Tài liệu mô tả test gì, test như nào (theo rule user)

---

### Output Directory

#### [NEW] `results/graphs/` directory
- Thư mục lưu ảnh PNG output từ visualizer

---

## Flow End-to-End

```
1. Setup hệ thống (ring, transport, publish index)
2. Chạy query → nhận QueryResult

3. MetricsCollector:
   snapshot_before = metrics.snapshot()
   stats = metrics.analyze_query(query_result)
   report = metrics.generate_report()

4. Churn:
   ring.remove_node(peer_id)
   ring.stabilize_all(rounds=3)
   snapshot_after = metrics.snapshot()
   delta = metrics.compare(snapshot_before, snapshot_after)

5. Visualizer:
   viz.draw_ring_topology("results/graphs/topology.png")
   viz.draw_query_path(query_result, "results/graphs/query_path.png")
   viz.draw_dht_distribution("results/graphs/dht_dist.png")
   viz.draw_churn_comparison(before_ring_state, after_ring_state, "results/graphs/churn.png")
```

---

## Verification Plan

### Automated Tests
```bash
cd e:\LEARN\HTPT\p2p_search
uv run pytest tests/test_metrics.py -v
uv run pytest tests/test_visualizer.py -v
```

### Integration Test
- Tạo ring 5 nodes → publish index → query → metrics.generate_report()
- Verify: total_messages > 0, messages_by_type đúng loại, avg_hops hợp lý (O(log N))
- Verify: visualizer tạo PNG files tồn tại và có kích thước > 0

### Churn Test
- Snapshot trước → remove 1 node → stabilize → snapshot sau → compare
- Verify: `ChurnDelta` phản ánh đúng sự thay đổi
- Verify: query sau churn vẫn đúng nhờ replica

### Manual Verification
- Mở file PNG xem có đúng ring topology không
- Kiểm tra query path highlight có đúng đường đi không




# Walkthrough: Metrics & Visualizer (Phase 3)

## Tổng quan

Triển khai 2 module mới cho Phase 3 — **metrics.py** (thống kê hiệu năng) và **visualizer.py** (vẽ topology mạng Chord) — hoàn toàn **zero-instrumentation**: chỉ ĐỌC dữ liệu sẵn có từ `transport.message_log` và `ChordRing` state, KHÔNG sửa bất kỳ module core nào.

## Files thay đổi

| File | Hành động | Mô tả |
|---|---|---|
| [pyproject.toml](file:///e:/LEARN/HTPT/p2p_search/pyproject.toml) | MODIFY | Thêm `networkx>=3.2`, `matplotlib>=3.8` |
| [metrics.py](file:///e:/LEARN/HTPT/p2p_search/src/metrics.py) | NEW | `MetricsCollector` + 4 dataclasses output |
| [visualizer.py](file:///e:/LEARN/HTPT/p2p_search/src/visualizer.py) | NEW | `NetworkVisualizer` + 4 phương thức vẽ |
| [test_metrics.py](file:///e:/LEARN/HTPT/p2p_search/tests/test_metrics.py) | NEW | 27 unit tests (7 nhóm) |
| [test_visualizer.py](file:///e:/LEARN/HTPT/p2p_search/tests/test_visualizer.py) | NEW | 15 unit tests (6 nhóm) |
| [README_metrics_visualizer.md](file:///e:/LEARN/HTPT/p2p_search/tests/README_metrics_visualizer.md) | NEW | Tài liệu mô tả test |

## Chi tiết module

### metrics.py — MetricsCollector

**Dataclasses đầu ra:**
- `QueryStats` — thống kê 1 query (hops, messages, early_stop)
- `NodeTraffic` — lưu lượng gửi/nhận per node
- `BatchMetrics` — báo cáo tổng hợp hệ thống
- `ChurnDelta` — so sánh trước/sau churn

**Phương thức chính:**
- `total_messages(start, end)` — đếm messages trong khoảng log
- `messages_by_type()` — phân loại FIND_SUCCESSOR, GET, PUT, ...
- `bandwidth_by_node()` — sent/received per node
- `analyze_query(QueryResult)` — phân tích chi tiết 1 query
- `generate_report()` → `BatchMetrics` — tổng hợp toàn bộ
- `snapshot()` + `compare(before, after)` → `ChurnDelta` — so sánh churn

### visualizer.py — NetworkVisualizer

**Phương thức vẽ:**
- `draw_ring_topology(path)` — vòng Chord + successor edges + finger shortcuts
- `draw_query_path(QueryResult, path)` — overlay routing path (mỗi keyword 1 màu)
- `draw_dht_distribution(path)` — bar chart keys per node (primary + replica)
- `draw_churn_comparison(removed_ids, path)` — ring sau churn + ghost nodes

**Dark theme** với bảng màu curated, tự động tạo thư mục output.

## Kết quả test

```
69 passed in 2.35s
```

- **27 metrics tests**: message counting, bandwidth, query analysis, DHT health, report, snapshot/compare, edge cases
- **15 visualizer tests**: init, topology PNG, query path, DHT distribution, churn, edge cases  
- **27 existing tests**: tất cả vẫn pass — zero regression

## Cách sử dụng

```python
from src.transport import LocalTransport
from src.chord.ring import ChordRing
from src.query_engine import QueryEngine
from src.metrics import MetricsCollector
from src.visualizer import NetworkVisualizer

# Setup
transport = LocalTransport()
ring = ChordRing.create([10, 60, 110, 160, 210], transport, m=8)

# Query
qe = QueryEngine(ring)
result = qe.query_and(10, "system AND database")

# Metrics
mc = MetricsCollector(transport, ring)
mc.add_query_result(result)
report = mc.generate_report()
print(report.to_dict())

# Visualizer
viz = NetworkVisualizer(ring)
viz.draw_ring_topology("results/graphs/topology.png")
viz.draw_query_path(result, "results/graphs/query_path.png")
viz.draw_dht_distribution("results/graphs/dht_dist.png")

# Churn
before = mc.snapshot()
ring.remove_node(60)
ring.stabilize_all(rounds=3)
after = mc.snapshot()
delta = mc.compare(before, after)
viz.draw_churn_comparison([60], "results/graphs/churn.png")
```

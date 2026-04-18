# PRD — Product Requirements Document
## Đề tài 64: Distributed Inverted Index — "P2P Library Search"

> **Phiên bản**: 2.1 (Transport Layer + Error Handling)  
> **Ngày**: 2026-04-16  
> **Tham chiếu BRD**: [BRD.md](file:///e:/LEARN/HTPT/docs/BRD.md)

---

## 1. Thiết Kế Kiến Trúc

### 1.1 Nguyên Tắc Cốt Lõi

> **Chord logic KHÔNG BIẾT peers nói chuyện kiểu gì.**  
> Mọi giao tiếp đi qua Transport interface.  
> Swap LocalTransport → NetworkTransport = zero thay đổi trong Chord.

### 1.2 Kiến Trúc 3 Lớp

```
┌──────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                        │
│                                                              │
│  demo.py / query_engine.py / indexer.py / visualizer.py      │
│  → Dùng ChordRing API, không biết transport                 │
└──────────────────────────┬───────────────────────────────────┘
                           │ uses
┌──────────────────────────▼───────────────────────────────────┐
│                     CHORD LOGIC LAYER                        │
│                                                              │
│  ChordNode: find_successor(), put(), get(), stabilize()      │
│  ChordRing: create, join, remove                             │
│                                                              │
│  → Giao tiếp qua self.transport.send(node_id, message)       │
│  → KHÔNG biết peer ở đâu (local object hay remote server)    │
│  → KHÔNG import socket, requests, flask                      │
└──────────────────────────┬───────────────────────────────────┘
                           │ calls
┌──────────────────────────▼───────────────────────────────────┐
│                     TRANSPORT LAYER                          │
│                                                              │
│  Transport (ABC)                                             │
│    ├── send(to_id, message, timeout_ms) → Response           │
│    └── PeerRegistry: node_id → address                       │
│                                                              │
│  ┌─────────────────┐          ┌──────────────────────┐       │
│  │ LocalTransport  │          │ NetworkTransport     │       │
│  │                 │          │                      │       │
│  │ address =       │          │ address =            │       │
│  │   object ref    │          │   "http://ip:port"   │       │
│  │                 │          │                      │       │
│  │ send() =        │          │ send() =             │       │
│  │   function call │          │   HTTP POST (FastAPI)│       │
│  │                 │          │                      │       │
│  │ timeout =       │          │ timeout =            │       │
│  │   ignored       │          │   requests.timeout   │       │
│  └─────────────────┘          └──────────────────────┘       │
│                                                              │
│  Phase 1: dùng LocalTransport                                │
│  Phase 2: swap sang NetworkTransport (không sửa Chord)       │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Mỗi Peer Lưu Gì (Hai Lớp Độc Lập)

```
┌──────────────────────────────────────────────────────┐
│                      MỖI PEER                        │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │ Document Store (phân chia TĨNH)               │    │
│  │   Peer i giữ doc [i*20 .. i*20+19]            │    │
│  │   Dùng để: trả content khi ai hỏi nội dung   │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │ DHT Index Store (phân chia BỞI HASH)          │    │
│  │   keyword → Set[doc_ids]                      │    │
│  │   hash(keyword) thuộc range nào → peer đó giữ │    │
│  │   Nhiều peer publish → merge (union)           │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │ Routing Metadata                              │    │
│  │   Finger Table (m entries) + Successor        │    │
│  │   + Predecessor                               │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │ Replica Store (backup từ predecessor)         │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ⚠️ Peer giữ doc 1-20 KHÔNG nhất thiết giữ index    │
│     của keyword trong doc đó! Hai lớp khác logic.    │
└──────────────────────────────────────────────────────┘
```

---

## 2. Transport Layer — Đặc Tả Chi Tiết

### 2.1 Message Protocol

```python
@dataclass
class Message:
    type: str           # loại message
    sender_id: int      # ai gửi
    payload: dict       # dữ liệu đính kèm

    # Các type hợp lệ:
    #   "FIND_SUCCESSOR"    payload: {"key": int}
    #   "GET_PREDECESSOR"   payload: {}
    #   "NOTIFY"            payload: {"node_id": int}
    #   "PUT"               payload: {"keyword": str, "doc_ids": [int]}
    #   "GET"               payload: {"keyword": str}
    #   "PING"              payload: {}
    #   "STORE_REPLICA"     payload: {"keyword": str, "doc_ids": [int]}
    #   "TRANSFER_KEYS"     payload: {"keys": {"keyword": [int]}}

@dataclass
class Response:
    success: bool
    data: dict          # kết quả trả về
    error: str | None   # thông báo lỗi nếu có
```

### 2.2 Transport Interface

```python
class Transport(ABC):
    """
    Interface giao tiếp giữa các peer.
    Chord logic chỉ gọi send() — không biết bên dưới là gì.
    """

    def __init__(self):
        self.registry: Dict[int, Any] = {}   # node_id → address
        self.message_log: List[Message] = [] # log mọi message (metrics)

    @abstractmethod
    def send(self, to_node_id: int, message: Message,
             timeout_ms: int = 5000) -> Response:
        pass

    def register(self, node_id: int, address: Any):
        """Đăng ký peer mới vào registry."""
        self.registry[node_id] = address

    def unregister(self, node_id: int):
        """Xóa peer khỏi registry (churn)."""
        del self.registry[node_id]
```

### 2.3 LocalTransport (Phase 1 — Simulation)

```python
class LocalTransport(Transport):
    """
    Peers giao tiếp bằng function call.
    registry: node_id → ChordNode object reference
    """

    def send(self, to_node_id, message, timeout_ms=5000):
        self.message_log.append(message)          # ghi log

        if to_node_id not in self.registry:
            return Response(success=False, data={},
                           error=f"Node {to_node_id} not found")

        target_node = self.registry[to_node_id]   # lấy object
        return target_node.handle_message(message) # function call
```

### 2.4 NetworkTransport (Phase 2 — FastAPI)

```python
class NetworkTransport(Transport):
    """
    Peers giao tiếp bằng HTTP POST.
    registry: node_id → "http://ip:port"
    """

    def send(self, to_node_id, message, timeout_ms=5000):
        self.message_log.append(message)

        if to_node_id not in self.registry:
            return Response(success=False, data={},
                           error=f"Node {to_node_id} not found")

        url = f"{self.registry[to_node_id]}/message"
        try:
            r = requests.post(url,
                            json=message.to_dict(),
                            timeout=timeout_ms / 1000)
            return Response.from_dict(r.json())
        except requests.Timeout:
            return Response(success=False, data={},
                           error="TIMEOUT")
        except requests.ConnectionError:
            return Response(success=False, data={},
                           error="NODE_UNREACHABLE")
```

### 2.5 Tại Sao Thiết Kế Như Vậy

| Quyết định | Lý do |
|---|---|
| `timeout_ms` ngay từ đầu | LocalTransport ignore nó, NetworkTransport dùng thật. Thêm sau = sửa interface |
| `message_log` trong Transport | Metrics "message overhead" có miễn phí — đếm len(message_log) |
| `PeerRegistry` trong Transport | Chord logic chỉ biết node_id. IP:port là chuyện của Transport |
| `handle_message()` trên ChordNode | Một entry point duy nhất cho mọi loại message — dễ thêm message type |
| `Response.error` field | Churn: node chết → Transport trả error → Chord xử lý retry |

---

## 3. Chord Logic Layer — Đặc Tả

### 3.1 ChordNode

```python
class ChordNode:
    # === Identity ===
    node_id: int                       # ID trên ring [0, 2^m)
    m: int                             # bit size (default 8)

    # === Transport (injected) ===
    transport: Transport               # KHÔNG biết local hay network

    # === Routing ===
    successor_id: int                  # ID, không phải object
    predecessor_id: int | None
    finger_table: List[int]            # List[node_id], size m

    # === Storage ===
    documents: Dict[int, ProcessedDoc] # doc_id → doc
    dht_store: Dict[str, Set[int]]     # keyword → {doc_ids}
    replica_store: Dict[str, Set[int]] # backup

    # === Methods ===
    def handle_message(msg: Message) → Response    # dispatcher
    def find_successor(key_id: int) → int          # O(log N) routing
    def closest_preceding_node(key_id: int) → int
    def put(keyword: str, doc_ids: Set[int]) → bool  # DHT store
    def get(keyword: str) → Set[int]               # DHT lookup
    def join(known_node_id: int)
    def stabilize()
    def fix_fingers()
    def notify(node_id: int)
```

**handle_message — Single Dispatcher:**
```python
def handle_message(self, message: Message) -> Response:
    handlers = {
        "FIND_SUCCESSOR": self._handle_find_successor,
        "GET_PREDECESSOR": self._handle_get_predecessor,
        "NOTIFY":          self._handle_notify,
        "PUT":             self._handle_put,
        "GET":             self._handle_get,
        "PING":            self._handle_ping,
        "STORE_REPLICA":   self._handle_store_replica,
        "TRANSFER_KEYS":   self._handle_transfer_keys,
    }
    handler = handlers.get(message.type)
    if not handler:
        return Response(False, {}, f"Unknown type: {message.type}")
    return handler(message.payload)
```

### 3.2 Routing — Giao Tiếp Qua Transport

```python
def find_successor(self, key_id: int) -> int:
    """Tìm peer chịu trách nhiệm key_id. Routing O(log N)."""
    if self._in_range(key_id, self.node_id, self.successor_id, 
                      inclusive_right=True):
        return self.successor_id

    n_prime = self.closest_preceding_node(key_id)

    if n_prime == self.node_id:
        return self.successor_id

    # ← ĐÂY LÀ ĐIỂM THEN CHỐT:
    # KHÔNG gọi: n_prime_object.find_successor(key_id)
    # MÀ gọi qua transport:
    response = self.transport.send(
        to_node_id=n_prime,
        message=Message("FIND_SUCCESSOR", self.node_id, {"key": key_id}),
        timeout_ms=5000
    )

    if not response.success:
        # Node chết → xử lý churn
        return self._handle_routing_failure(key_id, n_prime)

    return response.data["successor"]
```

> **Nhìn vào code trên**: không có dòng nào biết peer ở đâu. Chỉ có `transport.send(node_id, message)`. Local hay network đều chạy đúng.

### 3.3 ChordRing

```python
class ChordRing:
    nodes: Dict[int, ChordNode]
    transport: Transport               # shared transport
    m: int

    def create(num_peers, m, transport) → ChordRing
    def add_node(node_id) → ChordNode
    def remove_node(node_id)           # simulate churn
    def stabilize_all(rounds=3)
    def assign_documents(docs)
    def get_node(node_id) → ChordNode
```

---

## 4. Application Layer — Các Module

### Dependency Map

```
                 ┌──────────────┐
                 │   demo.py    │
                 └──────┬───────┘
            ┌───────────┼───────────┐
            ▼           ▼           ▼
    ┌───────────┐ ┌──────────┐ ┌──────────────┐
    │visualizer │ │  query   │ │   metrics    │
    │  .py      │ │ engine.py│ │    .py       │
    └───────────┘ └────┬─────┘ └──────┬───────┘
                       │              │
                       ▼              │ reads
                 ┌──────────┐        │
                 │ indexer  │    transport
                 │  .py     │    .message_log
                 └────┬─────┘        │
                      │              │
               ┌──────▼──────────────▼──────┐
               │     chord_ring.py          │
               │     chord_node.py          │
               └──────────┬─────────────────┘
                          │ calls
               ┌──────────▼─────────────────┐
               │     transport layer        │
               │  LocalTransport (phase 1)  │
               │  NetworkTransport (phase 2)│
               └────────────────────────────┘
                          │
               ┌──────────▼─────────────────┐
               │    preprocessing.py        │
               └────────────────────────────┘
```

### 4.1 `preprocessing.py`

| Function | Input | Output |
|---|---|---|
| `load_dataset(path)` | file path | `List[Dict]` |
| `clean_text(text)` | raw string | cleaned string |
| `tokenize(text)` | cleaned string | `List[str]` |
| `preprocess_all(docs)` | `List[Dict]` | `List[ProcessedDoc]` |

```python
@dataclass
class ProcessedDoc:
    id: int
    title: str
    category: str
    tokens: List[str]       # unique tokens sau clean
    raw_content: str        # giữ nguyên để fetch
```

### 4.2 `indexer.py`

```
BƯỚC A — Build Local Index (mỗi peer)
  Peer 0 đọc doc 1-20 → {"system": {1,5}, "node": {3,7}}

BƯỚC B — Publish vào DHT (qua transport!)
  peer.put("system", {1,5})
    → Băm "system" bằng deterministic_hash(SHA-1)
    → transport.send(target_peer_id, PUT message)
    → target peer: merge_put (union, không ghi đè)

BƯỚC C — Replicate
  target peer TỰ ĐỘNG gửi STORE_REPLICA → successor của nó (ngầm)

BƯỚC D — Churn (Handoff data)
  Khi node mới join, nó gửi notify.
  Predecessor cũ/mới tự tính lại khoảng, gửi TRANSFER_KEYS bàn giao lại dữ liệu.
```

### 4.3 `query_engine.py`

```python
@dataclass
class HopEvent:
    from_node: int
    to_node: int
    reason: str             # "ROUTE" | "FOUND" | "RETURN"

@dataclass
class KeywordLookup:
    keyword: str
    hash_value: int
    responsible_peer: int
    posting_list: Set[int]
    hops: List[HopEvent]
    hop_count: int

@dataclass
class QueryResult:
    raw_query: str
    keywords: List[str]
    initiator_peer: int
    lookups: List[KeywordLookup]
    final_result: Set[int]
    total_hops: int
    total_messages: int
    elapsed_ms: float
```

**AND Query Protocol:**
```
1. Parse: "system AND database" → ["system", "database"]
2. lookup("system"):
   initiator.find_successor(deterministic_hash("system"))
   → transport.send() → routing → target peer
   → target peer trả posting list
3. lookup("database"): tương tự
4. INTERSECT kết quả
5. Return QueryResult kèm trace
```

### 4.4 `metrics.py`

**Đo miễn phí nhờ Transport Layer:**

```python
class MetricsCollector:
    def __init__(self, transport: Transport):
        self.transport = transport

    def total_messages(self) -> int:
        return len(self.transport.message_log)

    def messages_by_type(self) -> Dict[str, int]:
        # đếm bao nhiêu FIND_SUCCESSOR, GET, PUT, ...

    def hops_for_query(self, query_trace) -> int:
        # từ trace, đếm hop

    def generate_report(self) -> BatchMetrics:
        # tổng hợp: avg hops, latency, success rate, ...
```

> **Không cần instrument Chord code** — Transport đã log hết. Đây là lợi ích lớn nhất của việc tách layer.

### 4.5 `visualizer.py`

- NetworkX: ring topology + finger table edges
- Highlight query path (màu khác nhau cho mỗi keyword)
- Label: peer ID, docs count, DHT keys count

---

## 5. Data Flow End-to-End

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: SETUP                               │
│                                                                 │
│  1. preprocessing.py → load + clean + tokenize 100 docs         │
│  2. Tạo Transport:                                              │
│       transport = LocalTransport()    # ← phase 1               │
│     # transport = NetworkTransport()  # ← phase 2 swap ở đây   │
│  3. chord_ring.py → tạo 5 peers, join, stabilize                │
│     mỗi peer nhận transport (inject)                            │
│  4. indexer.py → assign docs, build local index, publish DHT    │
│                                                                 │
│  ✅ Hệ thống sẵn sàng                                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    PHASE 2: QUERY                               │
│                                                                 │
│  query_engine.query_and("system AND database")                  │
│    → DHT lookup qua transport.send()                            │
│    → intersect → QueryResult + trace                            │
│  metrics → đọc transport.message_log → report                   │
│  visualizer → ring PNG + query path PNG                         │
│                                                                 │
│  ✅ Output: JSON trace + visualization                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    PHASE 3: CHURN TEST                          │
│                                                                 │
│  Remove Peer 2:                                                 │
│    transport.unregister(peer2_id)                               │
│    ring.remove_node(peer2_id)                                   │
│    ring.stabilize_all(rounds=3)                                 │
│  Chạy lại query → so sánh kết quả trước/sau                    │
│                                                                 │
│  ✅ Churn resilience demonstrated                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Error Handling & Failure Recovery

### 6.1 Phân Loại Lỗi Theo Tầng

```
┌──────────────────────────────────────────────────────────────┐
│  TẦNG 3: APPLICATION ERRORS                                 │
│  Lỗi logic ở query, index, preprocessing                    │
│  → Xử lý: validate input, trả kết quả rõ ràng              │
├──────────────────────────────────────────────────────────────┤
│  TẦNG 2: CHORD ROUTING ERRORS                               │
│  Lỗi routing: node chết giữa chừng, finger table stale,     │
│  routing loop                                                │
│  → Xử lý: retry with alternative finger, TTL, stabilize     │
├──────────────────────────────────────────────────────────────┤
│  TẦNG 1: TRANSPORT ERRORS                                   │
│  Lỗi giao tiếp: node unreachable, timeout, message corrupt  │
│  → Xử lý: trả Response(success=False, error=ERROR_CODE)     │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Error Codes Chuẩn Hóa

```python
class ErrorCode:
    # === Transport Layer ===
    NODE_NOT_FOUND    = "NODE_NOT_FOUND"      # node_id không có trong registry
    NODE_UNREACHABLE  = "NODE_UNREACHABLE"    # network: connection refused
    TIMEOUT           = "TIMEOUT"             # network: quá thời gian chờ
    
    # === Chord Layer ===
    ROUTING_FAILED    = "ROUTING_FAILED"      # không tìm được successor
    ROUTING_LOOP      = "ROUTING_LOOP"        # phát hiện loop (TTL hết)
    STALE_FINGER      = "STALE_FINGER"        # finger trỏ tới node đã chết
    KEY_NOT_FOUND     = "KEY_NOT_FOUND"       # keyword không tồn tại trong DHT
    
    # === Application Layer ===
    INVALID_QUERY     = "INVALID_QUERY"       # query rỗng hoặc sai format
    PARTIAL_FAILURE   = "PARTIAL_FAILURE"     # một số keyword lookup fail
    EMPTY_RESULT      = "EMPTY_RESULT"        # intersection rỗng (không phải lỗi)
    INDEX_BUILD_FAIL  = "INDEX_BUILD_FAIL"    # publish keyword thất bại
```

### 6.3 Tầng 1 — Transport Error Handling

| Lỗi | Khi nào xảy ra | Xử lý |
|---|---|---|
| `NODE_NOT_FOUND` | `send()` tới node_id không có trong registry | Trả `Response(success=False)` ngay, **không retry** |
| `NODE_UNREACHABLE` | Network: connection refused / DNS fail | Trả `Response(success=False)`, Chord layer quyết định retry |
| `TIMEOUT` | Network: response quá `timeout_ms` | Trả `Response(success=False)`, Chord layer quyết định retry |

**Nguyên tắc**: Transport KHÔNG retry. Nó chỉ báo cáo lỗi. Retry là trách nhiệm của Chord layer.

```python
# Transport luôn trả Response, KHÔNG raise exception
def send(self, to_node_id, message, timeout_ms=5000) -> Response:
    try:
        # ... gửi message
    except Exception as e:
        return Response(success=False, data={}, error=str(e))
    # KHÔNG BAO GIỜ: raise TransportError(...)
```

### 6.4 Tầng 2 — Chord Routing Error Handling

#### 6.4.1 Routing tới Node đã chết

```
Tình huống:
  Peer 0 muốn route tới key=73
  finger table nói: gửi tới Peer 2 (id=60)
  Nhưng Peer 2 đã chết!

Xử lý — _handle_routing_failure():
  1. Nhận Response(success=False) từ transport
  2. Đánh dấu finger entry = DEAD
  3. Thử finger entry tiếp theo (gần key nhất, vẫn sống)
  4. Nếu tất cả finger đều chết → fallback: gửi thẳng tới successor
  5. Nếu successor cũng chết → trả ROUTING_FAILED
```

```python
def _handle_routing_failure(self, key_id: int, dead_node_id: int) -> int:
    """Xử lý khi node trên đường route đã chết."""
    
    # Bước 1: thử các finger khác
    for i in range(self.m - 1, -1, -1):
        finger_id = self.finger_table[i]
        if finger_id == dead_node_id:
            continue  # skip node chết
        if not self._in_range(finger_id, self.node_id, key_id):
            continue
            
        response = self.transport.send(
            finger_id,
            Message("FIND_SUCCESSOR", self.node_id, {"key": key_id})
        )
        if response.success:
            return response.data["successor"]
    
    # Bước 2: fallback tới successor
    if self.successor_id != dead_node_id:
        response = self.transport.send(
            self.successor_id,
            Message("FIND_SUCCESSOR", self.node_id, {"key": key_id})
        )
        if response.success:
            return response.data["successor"]
    
    # Bước 3: hoàn toàn thất bại
    raise RoutingError(f"Cannot route to key {key_id}: all paths dead")
```

#### 6.4.2 Routing Loop Prevention (TTL)

```
Vấn đề:
  Peer 0 → Peer 2 → Peer 3 → Peer 0 → Peer 2 → ... (vô hạn)
  Có thể xảy ra khi finger table stale sau churn.

Giải pháp: TTL (Time-To-Live)
  Mỗi message mang theo ttl field.
  Mỗi hop giảm ttl đi 1.
  Khi ttl = 0 → dừng, trả ROUTING_LOOP error.
```

```python
@dataclass
class Message:
    type: str
    sender_id: int
    payload: dict
    ttl: int = 20          # ← MỚI: max 20 hops (đủ cho m=8, 256 nodes)

# Trong find_successor:
def _handle_find_successor(self, payload, ttl):
    if ttl <= 0:
        return Response(False, {}, ErrorCode.ROUTING_LOOP)
    
    # Forward với ttl - 1
    response = self.transport.send(
        n_prime,
        Message("FIND_SUCCESSOR", self.node_id, 
                {"key": key_id}, ttl=ttl - 1)   # ← giảm TTL
    )
```

> **Tại sao TTL=20?**  
> Chord routing = O(log N). Với N=256 nodes → max 8 hops lý thuyết.  
> TTL=20 → buffer rất thoải mái. Nếu đạt 20 hop → chắc chắn là loop.

#### 6.4.3 Stale Finger Table

```
Vấn đề:
  Peer 2 rời mạng → nhưng Peer 0 vẫn có Peer 2 trong finger table.
  Lần query tiếp → gửi tới Peer 2 → FAIL.

Giải pháp:
  1. Khi send() fail → đánh dấu finger entry = stale
  2. Dùng finger khác (6.4.1 đã xử lý)
  3. Background: chạy fix_fingers() periodic
     → cập nhật finger table bằng cách find_successor() lại
```

#### 6.4.4 Key Not Found trong DHT

```
Tình huống:
  lookup("xyzabc123") → routing thành công → đến đúng peer
  Nhưng peer đó không có keyword này trong dht_store.

Xử lý:
  → Trả posting_list = emtpy set (KHÔNG phải error!)
  → Đây là kết quả hợp lệ: "không tài liệu nào chứa từ này"
  → Query engine: intersect với empty set → final result = empty
```

```python
def _handle_get(self, payload):
    keyword = payload["keyword"]
    doc_ids = self.dht_store.get(keyword, set())  # empty nếu không có
    return Response(
        success=True,
        data={"keyword": keyword, "doc_ids": list(doc_ids)},
        error=None
    )
```

### 6.5 Tầng 3 — Application Error Handling

#### 6.5.1 Preprocessing Errors

| Lỗi | Xử lý | Severity |
|---|---|---|
| File JSON không tồn tại | Raise `FileNotFoundError` + log rõ path | ❌ Fatal |
| JSON malformed (parse fail) | Raise `ValueError` + log nội dung lỗi | ❌ Fatal |
| Doc thiếu field `content` | Skip doc, log warning, tiếp tục | ⚠️ Warning |
| Doc thiếu field `id` | Skip doc, log warning | ⚠️ Warning |
| `id` trùng lặp | Giữ cái đầu tiên, skip duplicate, log | ⚠️ Warning |
| `content` rỗng/null | Skip doc, log | ⚠️ Warning |
| Encoding error | Try UTF-8, fallback Latin-1, log | ⚠️ Warning |

**Nguyên tắc**: Lỗi ở 1 doc không crash toàn bộ pipeline. Pipeline trả report rõ ràng.

```python
@dataclass
class PreprocessingReport:
    total_raw: int              # số doc trong file
    total_valid: int            # số doc qua validation thành công
    total_skipped: int          # số doc bị skip
    skip_reasons: List[str]     # lý do skip từng doc
    vocabulary_size: int        # số keyword unique
    warnings: List[str]
```

#### 6.5.2 Query Errors

| Lỗi | Xử lý | Trả về |
|---|---|---|
| Query rỗng `""` | Validate trước, trả lỗi ngay | `QueryResult(error=INVALID_QUERY)` |
| Keyword chỉ có stopwords | Sau clean → keywords list rỗng | `QueryResult(error=INVALID_QUERY, detail="all keywords are stopwords")` |
| 1 keyword lookup fail, 1 OK | Trả kết quả partial + warning | `QueryResult(warnings=["keyword 'xyz' lookup failed"])` |
| Tất cả keyword lookup fail | Trả error rõ ràng | `QueryResult(error=ROUTING_FAILED)` |
| Intersection rỗng | **Không phải lỗi** — kết quả hợp lệ | `QueryResult(final_result=set(), status="SUCCESS")` |

```python
@dataclass
class QueryResult:
    raw_query: str
    keywords: List[str]
    initiator_peer: int
    lookups: List[KeywordLookup]
    final_result: Set[int]
    total_hops: int
    total_messages: int
    elapsed_ms: float
    # === ERROR HANDLING FIELDS (MỚI) ===
    status: str              # "SUCCESS" | "PARTIAL" | "FAILED"
    warnings: List[str]      # non-fatal issues
    error: str | None        # fatal error code nếu có
```

#### 6.5.3 Index Build Errors

| Lỗi | Khi nào | Xử lý |
|---|---|---|
| Publish keyword fail (target node chết) | Churn xảy ra giữa lúc build index | Retry 1 lần sau stabilize, nếu vẫn fail → log warning, tiếp tục |
| merge_put conflict | Không xảy ra vì union luôn idempotent | — |
| Peer không có docs nào | Peer mới join, chưa assigned | Skip peer đó, log | 

### 6.6 Retry Strategy

```
┌──────────────────────────────┐
│       RETRY POLICY           │
│                              │
│  Transport Layer:  0 retry   │
│    → chỉ report lỗi         │
│                              │
│  Chord Layer:      1 retry   │
│    → thử finger khác        │
│    → fallback tới successor │
│    → nếu vẫn fail → error   │
│                              │
│  Application:      0 retry   │
│    → trả kết quả + warning  │
│    → user quyết định retry  │
└──────────────────────────────┘

Tại sao không retry nhiều lần?
  → Trong simulation: node chết = chết luôn (không restart)
  → Retry nhiều = lãng phí, vì node sẽ không sống lại
  → 1 retry qua finger khác là đủ trong hầu hết trường hợp
```

### 6.7 Churn — Dòng Chảy Lỗi End-to-End

```
Peer 2 rời mạng:
  │
  ├─[1] transport.unregister(peer2_id)
  │     → registry xóa Peer 2
  │
  ├─[2] Peer 0 gửi query, finger table trỏ tới Peer 2:
  │     → transport.send(peer2_id, msg)
  │     → Response(success=False, error="NODE_NOT_FOUND")
  │
  ├─[3] ChordNode._handle_routing_failure(key, peer2_id):
  │     → thử finger khác → thành công → tiếp tục routing
  │     HOẶC
  │     → tất cả finger fail → fallback successor → thành công
  │     HOẶC  
  │     → successor cũng chết → raise RoutingError
  │
  ├─[4] QueryEngine bắt RoutingError:
  │     → Ghi warning vào QueryResult
  │     → Nếu chỉ 1 keyword fail: status = "PARTIAL"
  │     → Nếu tất cả fail: status = "FAILED"
  │
  ├─[5] Nếu keyword nằm trong replica_store của successor:
  │     → GET từ successor thay vì node chết → thành công!
  │     → Đây là lý do cần replication r=2
  │
  └─[6] ring.stabilize_all(rounds=3):
        → fix successor/predecessor pointers
        → fix_fingers() cập nhật finger table
        → Các query SAU stabilize sẽ không gặp lỗi nữa
```

### 6.8 Tổng Kết Error Handling

| Scenario | Phát hiện bởi | Xử lý | User thấy gì |
|---|---|---|---|
| Node chết, routing fail | Transport → Chord | Thử finger khác | Query chậm hơn nhưng vẫn đúng |
| Routing loop | TTL=0 | Dừng routing, trả error | Warning trong trace |
| Keyword không tồn tại | DHT GET → empty | Trả empty set (hợp lệ) | "0 documents found" |
| Query rỗng/invalid | QueryEngine validate | Trả error ngay | Error message rõ ràng |
| Partial keyword failure | QueryEngine | Trả kết quả partial + warning | Partial result + warning |
| JSON file lỗi | Preprocessing | Fatal error, dừng | Error log + exit |
| 1 doc lỗi trong dataset | Preprocessing | Skip doc, log | Report nói rõ skip bao nhiêu |
| All fingers dead | Chord fallback chain | RoutingError | Query FAILED |
| Replica cũng mất | Churn quá nặng | Data loss (chấp nhận) | Warning: "data may be incomplete" |

---

## 7. Phase 2 — Network Demo (FastAPI)

> Phase 2 chỉ cần làm khi Phase 1 xong hoàn toàn.  
> Không sửa bất kỳ dòng nào trong Chord logic.

### 6.1 Kiến Trúc Network

```
Terminal 1:                 Terminal 2:               Terminal 3:
  python peer.py            python peer.py            python peer.py
    --node-id 10              --node-id 60              --node-id 110
    --port 8001               --port 8002               --port 8003
    --bootstrap               --join 10                 --join 10
     localhost:8001

Mỗi peer = 1 FastAPI server
Giao tiếp: HTTP POST giữa các port
```

### 6.2 FastAPI Peer Server

```python
# peer_server.py — chạy độc lập mỗi terminal
from fastapi import FastAPI
app = FastAPI()

node = ChordNode(node_id, transport=NetworkTransport())

@app.post("/message")
def receive_message(msg: dict):
    message = Message.from_dict(msg)
    response = node.handle_message(message)
    return response.to_dict()
```

### 6.3 Chuyển Đổi Local → Network

```python
# === Phase 1: Local ===
transport = LocalTransport()
ring = ChordRing.create(num_peers=5, m=8, transport=transport)

# === Phase 2: Network ===
transport = NetworkTransport()
transport.register(10,  "http://localhost:8001")
transport.register(60,  "http://localhost:8002")
transport.register(110, "http://localhost:8003")
# ChordNode code: KHÔNG THAY ĐỔI GÌ
```

> **Chỉ thay 1 dòng**: `LocalTransport()` → `NetworkTransport()` + register peers.

---

## 8. Cấu Trúc Thư Mục

```
e:\LEARN\HTPT\
│
├── docs/
│   ├── BRD.md
│   └── PRD.md                          # file này
│
├── dataset/
│   ├── p2p_library_100_stories.json    # raw input
│   └── processed/                      # output preprocessing
│       ├── processed_docs.json
│       ├── inverted_index.json
│       ├── peer_local_indexes.json
│       └── preprocessing_report.json
│
├── src/
│   ├── __init__.py
│   ├── models.py                       # Message, Response, ProcessedDoc, etc.
│   ├── transport.py                    # Transport ABC + LocalTransport
│   ├── network_transport.py            # NetworkTransport (phase 2)
│   ├── preprocessing.py
│   ├── chord_node.py
│   ├── chord_ring.py
│   ├── indexer.py
│   ├── query_engine.py
│   ├── metrics.py
│   └── visualizer.py
│
├── tests/
│   ├── __init__.py
│   ├── README.md
│   ├── test_transport.py               # test message passing
│   ├── test_preprocessing.py
│   ├── test_chord.py
│   ├── test_indexer.py
│   ├── test_query.py
│   └── test_metrics.py
│
├── results/
│   ├── traces/
│   └── graphs/
│
├── demo_local.py                       # Phase 1: local simulation
├── peer_server.py                      # Phase 2: FastAPI per-peer server
└── requirements.txt
```

---

## 9. Trace Output Format (Deliverable Chính)

```json
{
  "query": "system AND database",
  "initiator_peer": 10,
  "transport_mode": "local",
  "timestamp": "2026-04-16T12:00:00",

  "keyword_lookups": [
    {
      "keyword": "system",
      "hash_value": 73,
      "routing_path": [
        {"hop": 1, "from": 10, "to": 60, "reason": "finger[2] closest to 73"},
        {"hop": 2, "from": 60, "to": 110, "reason": "successor(73) = Node110"}
      ],
      "responsible_peer": 110,
      "posting_list": [5, 21, 67],
      "hops": 2
    },
    {
      "keyword": "database",
      "hash_value": 155,
      "routing_path": [
        {"hop": 1, "from": 10, "to": 110, "reason": "finger[3] closest to 155"}
      ],
      "responsible_peer": 200,
      "posting_list": [8, 21, 55],
      "hops": 1
    }
  ],

  "intersection": [21],
  "total_hops": 3,
  "total_messages": 6,
  "elapsed_ms": 2.5,
  "peers_contacted": [10, 60, 110, 200],
  "peers_not_contacted": [30]
}
```

---

## 10. Acceptance Criteria

### AC-1: Transport Layer
- [ ] Transport ABC với send(), register(), unregister()
- [ ] LocalTransport: function call hoạt động đúng
- [ ] message_log ghi lại mọi message
- [ ] timeout_ms parameter tồn tại (LocalTransport ignore, interface sẵn sàng)
- [ ] Chord code: 0 import socket/requests/flask

### AC-2: Preprocessing
- [ ] Load 100 docs, validate, clean, tokenize
- [ ] Output: processed_docs.json, inverted_index.json

### AC-3: Chord DHT
- [ ] find_successor() routing O(log N) qua transport.send()
- [ ] finger table build đúng
- [ ] handle_message() dispatch đúng message type
- [ ] Unit test: routing từ bất kỳ peer nào đều tìm đúng successor

### AC-4: Distributed Index
- [ ] Mỗi peer build local index từ docs CỦA MÌNH
- [ ] Publish vào DHT qua transport (merge_put, union)
- [ ] DHT store ≡ global inverted index (ground truth verify)

### AC-5: AND Query
- [ ] Parse "A AND B AND C" → keywords
- [ ] DHT lookup qua transport → intersect
- [ ] Kết quả khớp brute-force search
- [ ] JSON trace output đúng format

### AC-6: Churn
- [ ] Remove 1 peer → transport.unregister + stabilize
- [ ] Query vẫn đúng nhờ replica
- [ ] Metrics trước/sau churn

### AC-7: Metrics & Visualization
- [ ] Metrics đọc từ transport.message_log (không instrument Chord)
- [ ] NetworkX topology + query path highlighted

### AC-8: Network Demo (bonus)
- [ ] NetworkTransport gọi HTTP POST tới FastAPI peer server
- [ ] Cùng bộ test, swap transport, kết quả giống nhau

### AC-9: Error Handling
- [ ] Transport trả Response(success=False) khi node chết, KHÔNG raise exception
- [ ] Chord: routing failure → thử finger khác → fallback successor
- [ ] TTL=20 trên Message, routing loop bị phát hiện và dừng
- [ ] Query rỗng/invalid → trả error ngay, không routing
- [ ] Partial failure: 1 keyword fail → trả partial result + warning
- [ ] Preprocessing: 1 doc lỗi → skip + log, pipeline tiếp tục
- [ ] Churn: sau stabilize, query không gặp stale finger nữa
- [ ] Unit test: inject node failure → verify retry + fallback hoạt động

---

## 11. Lộ Trình

```
Phase 1: Foundation (3 ngày)
  ├── models.py (Message, Response, dataclasses)
  ├── transport.py (ABC + LocalTransport) + tests
  ├── preprocessing.py + tests
  ├── chord_node.py + tests              ← CRITICAL PATH
  └── chord_ring.py + tests

Phase 2: Core Logic (2 ngày)
  ├── indexer.py + tests
  └── query_engine.py + tests

Phase 3: Polish (2 ngày)
  ├── metrics.py
  ├── visualizer.py
  ├── churn simulation
  └── demo_local.py

Phase 4: Network Demo (1 ngày, bonus)
  ├── network_transport.py
  ├── peer_server.py (FastAPI)
  └── test swap transport

Phase 5: Delivery (1 ngày)
  ├── Report / Slides
  └── Demo run + screenshots
```

---

## 12. Tradeoff Summary

| Quyết định | Chọn | Bỏ | Lý do |
|---|---|---|---|
| Architecture | **Transport Layer abstraction** | Direct function call | Swap local↔network không sửa Chord |
| DHT | **Chord** | Kademlia | Đơn giản, pseudocode rõ |
| Message format | **Dict/JSON** | Protobuf | Dễ debug, dễ serialize HTTP |
| Timeout | **Có ngay từ đầu** | Thêm sau | Tránh sửa interface |
| Addressing | **node_id only** trong Chord | ip:port | ip:port là chuyện của Transport |
| Network demo | **FastAPI** | Flask, gRPC | Async-ready, auto docs, modern |
| Query | **Sequential** | Parallel | Trace rõ ràng |
| Replication | **r=2** | r=1, r=3 | Cân bằng overhead vs tolerance |
| Metrics | **Đọc từ transport.message_log** | Instrument Chord | Zero coupling, miễn phí |

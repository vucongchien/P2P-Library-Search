# Phase 4: Network Demo + Web Dashboard — Final Plan

## Mục Tiêu

Chuyển P2P Chord DHT sang **HTTP thật** (mỗi peer = 1 terminal) + xây **Web Dashboard** bằng React + Tailwind hiển thị **toàn bộ** hoạt động: routing, DHT state, finger tables, message log, metrics, churn — không che giấu gì.

---

## UI Design Mockup

![Dashboard Mockup](C:\Users\123ch\.gemini\antigravity\brain\44759436-fd59-4420-86b4-7a3cf88b8a27\dashboard_mockup_1776596411235.png)

---

## Trả Lời Câu Hỏi Scalability

### Peer Server có scale được không?

**Có.** Mỗi `peer_server.py` là **hoàn toàn độc lập**:

```bash
# Scale thêm peer — chỉ cần mở terminal mới:
python peer_server.py --node-id 150 --port 8006 --m 8

# Rồi từ Dashboard: Register peer mới → Join → Stabilize
```

**Cơ chế scale:**
1. Peer mới start → chỉ biết mỗi port của mình
2. Dashboard gửi `/api/register-peers` → peer biết các peer khác
3. Dashboard gửi `/api/join` với `known_node_id` → Chord join protocol chạy qua HTTP
4. Dashboard gửi `/api/stabilize` cho tất cả → ring tự cân bằng
5. Peer mới xuất hiện trên Dashboard tự động

**Giới hạn**: Chord DHT m=8 → max 256 nodes. Thực tế demo 5-10 nodes là đủ.

---

## Kiến Trúc

```
┌──────────────────────────────────────────────────────────┐
│  Browser: http://localhost:5173  (Vite dev server)       │
│  React + Tailwind SPA                                    │
│  Proxy /api/* → http://localhost:9000                    │
└─────────────────────┬────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────┐
│  Dashboard Backend: http://localhost:9000                 │
│  dashboard_server.py (FastAPI)                           │
│  - Aggregator: poll N peers, merge state                 │
│  - Proxy: forward queries/commands to peers              │
│  - Serves: static build files (production)               │
└─────────┬──────────┬──────────┬──────────┬──────────────┘
          │          │          │          │
    ┌─────▼──┐ ┌─────▼──┐ ┌─────▼──┐ ┌─────▼──┐
    │Peer:8001│ │Peer:8002│ │Peer:8003│ │Peer:8004│  ...scalable
    │Node 10  │ │Node 60  │ │Node 110 │ │Node 160 │
    │ChordNode│ │ChordNode│ │ChordNode│ │ChordNode│
    │NetTransp│ │NetTransp│ │NetTransp│ │NetTransp│
    └─────────┘ └─────────┘ └─────────┘ └─────────┘
        ◄────── HTTP POST /message ──────►
```

---

## Component Breakdown — React

### Layout tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Title + Status + Action Buttons                       │
├───────────────────────────┬─────────────────────────────────────┤
│                           │                                     │
│   ChordRingViz            │   QueryPanel                        │
│   (SVG circle topology)   │   Input + Results + Routing Trace   │
│   Nodes + links           │                                     │
│   Highlight on query      │─────────────────────────────────────│
│                           │                                     │
│                           │   LogPanel                           │
│                           │   All messages/events, timestamped  │
│                           │   Filterable by type, node          │
│                           │                                     │
├───────────────────────────┴─────────────────────────────────────┤
│                                                                 │
│  PeerList — Grid of PeerCards (1 card per peer)                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ PeerCard   │ │ PeerCard   │ │ PeerCard   │ │ PeerCard   │  │
│  │ N10        │ │ N60        │ │ N110       │ │ N160       │  │
│  │ Full state │ │ Full state │ │ Full state │ │ Full state │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  MetricsBar — Aggregate stats (Total msgs, Avg hops, ...)      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Tree

```
App
├── Header
│   ├── Title + Ring Status Badge (🟢 Stable / 🟡 Stabilizing / 🔴 Error)
│   └── ActionBar
│       ├── Button: Register Peers
│       ├── Button: Join Ring  
│       ├── Button: Stabilize
│       ├── Button: Publish Data
│       └── Button: Add Node / Remove Node (dropdown)
│
├── MainGrid (2 columns)
│   ├── Left: ChordRingViz
│   │   └── SVG circle with:
│   │       - Node circles (positioned by hash on ring)
│   │       - Successor arrows (solid blue)
│   │       - Predecessor arrows (dashed gray)  
│   │       - Finger table links (dotted, on hover)
│   │       - Node tooltip on hover (successor, predecessor, dht count)
│   │       - Highlight active routing path after query
│   │
│   └── Right: (stacked)
│       ├── QueryPanel
│       │   ├── Input: query text
│       │   ├── Select: initiator peer
│       │   ├── Button: Run Query
│       │   └── QueryResult
│       │       ├── RoutingTrace (per keyword)
│       │       │   └── HopStep (from → to, action, reason)
│       │       ├── Intersection display
│       │       └── Summary (hops, messages, latency)
│       │
│       └── LogPanel
│           ├── Filter bar (by message type, by node)
│           ├── Log entries (virtual scroll)
│           │   └── LogEntry (timestamp, from→to, type, payload preview)
│           └── Controls: Clear, Pause, Auto-scroll toggle
│
├── PeerList
│   └── PeerCard[] (grid, 1 per peer)
│       ├── Header: Node ID + Status Badge
│       ├── Section: Network (successor, predecessor)
│       ├── Section: Finger Table (table format, m entries)
│       ├── Section: DHT Store (keyword → [doc_ids], expandable)
│       ├── Section: Replica Store (keyword → [doc_ids])
│       ├── Section: Local Index (keyword → [doc_ids])  
│       ├── Section: Stats (total messages sent/received, dht key count)
│       └── Footer: Last updated timestamp
│
└── MetricsBar
    ├── Total Messages
    ├── Average Hops per Query
    ├── Success Rate
    ├── Messages by Type (mini breakdown)
    └── Per-Node Traffic (mini bar)
```

### Mỗi PeerCard hiển thị ĐẦY ĐỦ:

```
┌─────────────────────────────────────────────┐
│  🟢 Node 10                    Port: 8001  │
├─────────────────────────────────────────────┤
│  NETWORK                                    │
│  Successor:    N60                          │
│  Predecessor:  N210                         │
├─────────────────────────────────────────────┤
│  FINGER TABLE                               │
│  [0] start=11   → N60                      │
│  [1] start=12   → N60                      │
│  [2] start=14   → N60                      │
│  [3] start=18   → N60                      │
│  [4] start=26   → N60                      │
│  [5] start=42   → N60                      │
│  [6] start=74   → N110                     │
│  [7] start=138  → N160                     │
├─────────────────────────────────────────────┤
│  DHT STORE (3 keywords)                     │
│  ┌─────────────┬──────────────────────┐     │
│  │ distributed │ [2, 5, 21]           │     │
│  │ network     │ [1, 5, 20, 21]       │     │
│  │ protocol    │ [20, 22]             │     │
│  └─────────────┴──────────────────────┘     │
├─────────────────────────────────────────────┤
│  REPLICA STORE (2 keywords)                 │
│  ┌─────────────┬──────────────────────┐     │
│  │ algorithm   │ [41, 42]             │     │
│  │ search      │ [31, 32, 40, 42]     │     │
│  └─────────────┴──────────────────────┘     │
├─────────────────────────────────────────────┤
│  LOCAL INDEX (4 keywords)                   │
│  ┌─────────────┬──────────────────────┐     │
│  │ system      │ [1, 2, 5]            │     │
│  │ database    │ [1, 2, 3]            │     │
│  │ network     │ [1, 5]               │     │
│  │ distributed │ [2, 5]               │     │
│  └─────────────┴──────────────────────┘     │
├─────────────────────────────────────────────┤
│  STATS                                      │
│  Messages: 47 sent / 32 received            │
│  DHT Keys: 3 | Replica Keys: 2             │
│  Last Updated: 17:31:05                     │
└─────────────────────────────────────────────┘
```

---

## Proposed File Changes

### Component 1: Network Transport

#### [NEW] `src/network_transport.py`
- `NetworkTransport(Transport)` — `send()` bằng `httpx.Client` sync
- `registry: {node_id: "http://127.0.0.1:{port}"}`
- Error mapping: `ConnectError → NODE_UNREACHABLE`, `TimeoutException → TIMEOUT`
- Connection pooling via shared `httpx.Client`
- `close()` method

---

### Component 2: Peer Server

#### [NEW] `peer_server.py`

CLI:
```bash
python peer_server.py --node-id 10 --port 8001 --m 8
```

Endpoints:

| Method | Path | Mô tả |
|---|---|---|
| POST | `/message` | Chord protocol messages (peer↔peer) |
| POST | `/api/register-peers` | Nhận `{node_id: url, ...}` → update transport registry |
| POST | `/api/join` | `{known_node_id: int}` → trigger `node.join()` |
| POST | `/api/stabilize` | Trigger 1 round stabilize + fix_fingers + check_predecessor |
| POST | `/api/publish` | `{data: {keyword: [doc_ids]}}` → load_local_index + publish |
| POST | `/api/query` | `{query: str}` → chạy get() cho từng keyword, trả full trace |
| GET | `/api/state` | **FULL state dump** — tất cả dữ liệu peer đang giữ |
| GET | `/api/messages` | Message log (with optional `?since=timestamp`) |
| GET | `/health` | Quick liveness check |

**`/api/state` response** (siêu đầy đủ):
```json
{
  "node_id": 10,
  "port": 8001,
  "m": 8,
  "successor": 60,
  "predecessor": 210,
  "finger_table": [
    {"index": 0, "start": 11, "node": 60},
    {"index": 1, "start": 12, "node": 60},
    ...
  ],
  "dht_store": {
    "network": [1, 5, 20, 21],
    "distributed": [2, 5, 21]
  },
  "replica_store": {
    "algorithm": [41, 42]
  },
  "local_index": {
    "system": [1, 2, 5],
    "database": [1, 2, 3]
  },
  "stats": {
    "dht_key_count": 3,
    "replica_key_count": 2,
    "local_keyword_count": 4,
    "message_count": 47
  },
  "status": "ok"
}
```

---

### Component 3: Dashboard Backend

#### [NEW] `dashboard/backend/dashboard_server.py`

FastAPI aggregator — biết danh sách tất cả peers.

```bash
python dashboard_server.py --peers "10:8001,60:8002,110:8003,160:8004,210:8005" \
                           --data-file "../p2p_library_100_stories.json"
```

Endpoints:

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/ring-state` | Aggregate `/api/state` từ tất cả peers → combined |
| POST | `/api/setup/register` | Gửi peer list tới tất cả peers |
| POST | `/api/setup/join` | Join tuần tự (peer 1 bootstrap, peer 2+ join via peer 1) |
| POST | `/api/setup/stabilize` | Stabilize N rounds cho tất cả peers |
| POST | `/api/setup/publish` | Phân chia data từ JSON file → publish cho mỗi peer |
| POST | `/api/query` | Forward tới 1 peer, return full trace |
| POST | `/api/churn/remove` | Unregister 1 peer khỏi tất cả peers còn lại |
| POST | `/api/churn/add` | Register peer mới + join + stabilize |
| GET | `/api/messages/all` | Aggregate message logs từ tất cả peers |
| GET | `/api/metrics` | Tính toán metrics tổng hợp |
| GET | `/api/data-preview` | Preview data từ JSON file (cho UI biết publish cái gì) |

**Data Loading**: Dashboard đọc `p2p_library_100_stories.json`, phân chia documents cho N peers (round-robin), rồi gửi `/api/publish` cho mỗi peer kèm local index đã build sẵn.

---

### Component 4: Dashboard Frontend

#### [NEW] `dashboard/frontend/` — Vite + React + Tailwind v3

```
dashboard/frontend/
├── index.html
├── vite.config.js          # proxy /api → localhost:9000
├── tailwind.config.js
├── postcss.config.js
├── package.json
└── src/
    ├── main.jsx
    ├── App.jsx              # Layout + state management
    ├── api.js               # HTTP client (fetch wrapper)
    ├── components/
    │   ├── Header.jsx       # Title + status + action buttons
    │   ├── ChordRingViz.jsx # SVG ring topology
    │   ├── QueryPanel.jsx   # Query input + routing trace display
    │   ├── LogPanel.jsx     # Message/event log with filters
    │   ├── PeerList.jsx     # Grid container for PeerCards
    │   ├── PeerCard.jsx     # Full detail card for 1 peer
    │   ├── MetricsBar.jsx   # Aggregate metrics display
    │   └── Controls.jsx     # Setup wizard + churn controls
    └── hooks/
        ├── usePolling.js    # Generic polling hook
        └── useRingState.js  # Fetch + cache ring state
```

---

## Data Flow: Từ JSON File → DHT

```
p2p_library_100_stories.json (100 docs)
  ↓
Dashboard backend reads file
  ↓
Split docs round-robin → 5 groups:
  Peer 10:  docs [0,5,10,15,...] → 20 docs
  Peer 60:  docs [1,6,11,16,...] → 20 docs
  Peer 110: docs [2,7,12,17,...] → 20 docs
  Peer 160: docs [3,8,13,18,...] → 20 docs
  Peer 210: docs [4,9,14,19,...] → 20 docs
  ↓
Tokenize + Build local inverted index per group
  ↓
POST /api/publish → mỗi peer nhận keyword → doc_ids mapping
  ↓
Peer calls node.load_local_index() + node.publish()
  ↓
publish() → mỗi keyword: 
  find_successor(hash(keyword)) qua HTTP → target peer
  PUT message qua HTTP → target peer merge_put
  ↓
DHT hoàn chỉnh, query sẵn sàng
```

---

## Lỗi Tiềm Ẩn Theo Từng Bước

### Bước 1: Start Peer Servers

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Port đã bị chiếm | Process cũ chưa tắt | Check port trước khi bind, log rõ |
| Python path error | `src` module not found | Chạy từ `p2p_search/` directory, dùng relative import |
| Encoding error (Windows) | UTF-8 stdout | `sys.stdout.reconfigure(encoding='utf-8')` |

### Bước 2: Register Peers

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Peer chưa start xong | Race condition | Dashboard retry + health check trước |
| Self-registration | Peer register chính mình | Filter out self từ peer list |

### Bước 3: Join Ring

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Join order sai | Peer 2 join trước Peer 1 bootstrap | Join tuần tự, peer 1 luôn đầu tiên |
| FIND_SUCCESSOR fail qua HTTP | Target peer chưa sẵn sàng | Retry 3 lần với backoff |
| Circular successor | Join đúng nhưng finger table chưa fix | Stabilize đủ rounds (≥ m) |

### Bước 4: Stabilize

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Interleaved stabilize | Nhiều peers stabilize đồng thời → race | Uvicorn 1 worker = serialize. Chạy tuần tự từ Dashboard |
| Finger table incomplete | Chưa đủ rounds | Chạy m rounds (m=8) |
| Data handoff fail | transfer_keys qua HTTP timeout | Tăng timeout cho bulk transfer |

### Bước 5: Publish

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Large payload | 100 docs → nhiều keywords | Chunk publish, không publish tất cả cùng lúc |
| Keyword routing sai | Finger table stale | Đảm bảo stabilize xong trước khi publish |
| Duplicate publish | Retry publish → double data | merge_put (union) → idempotent, safe |

### Bước 6: Query qua Dashboard

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Trace data mất qua HTTP | Serialize/Deserialize `RoutingTrace` | Đã handle: `to_dict()` / `from_dict()` |
| CORS blocked | Dashboard frontend ≠ peer server origin | Dashboard backend proxy, không gọi peer trực tiếp từ browser |
| Timeout trên multi-hop | Mỗi hop = 1 HTTP round-trip, tích lũy latency | Tăng overall timeout, TTL=20 đủ |

### Bước 7: Churn

| Lỗi | Nguyên nhân | Phòng tránh |
|---|---|---|
| Process thật sự chết vs unregister | Kill process ≠ unregister ở peers khác | Dashboard phải notify tất cả peers còn lại xóa node chết khỏi registry |
| Data loss | Node chết mang theo DHT data | Replica store ở successor → recovery |
| Stale finger table | Peers còn trỏ tới node chết | Stabilize sau churn → fix_fingers |

---

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "networkx>=3.2",
    "matplotlib>=3.8",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "httpx>=0.28",
]
```

```json
// dashboard/frontend/package.json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4",
    "autoprefixer": "^10",
    "postcss": "^8",
    "tailwindcss": "^3",
    "vite": "^5"
  }
}
```

---

## Cấu Trúc Thư Mục Cuối Cùng

```
p2p_search/
├── src/
│   ├── models/                      # (không đổi)  
│   ├── chord/                       # (không đổi)
│   ├── transport.py                 # (không đổi)
│   ├── network_transport.py         # [NEW]
│   ├── query_engine.py              # (không đổi)
│   ├── metrics.py                   # (không đổi)
│   ├── visualizer.py                # (không đổi)
│   └── churn_simulation.py          # (không đổi)
│
├── dashboard/
│   ├── backend/
│   │   └── dashboard_server.py      # [NEW] FastAPI aggregator
│   └── frontend/                    # [NEW] Vite + React + Tailwind
│       ├── src/
│       │   ├── App.jsx
│       │   ├── api.js
│       │   ├── components/
│       │   │   ├── Header.jsx
│       │   │   ├── ChordRingViz.jsx
│       │   │   ├── QueryPanel.jsx
│       │   │   ├── LogPanel.jsx
│       │   │   ├── PeerList.jsx
│       │   │   ├── PeerCard.jsx
│       │   │   ├── MetricsBar.jsx
│       │   │   └── Controls.jsx
│       │   └── hooks/
│       │       ├── usePolling.js
│       │       └── useRingState.js
│       ├── vite.config.js
│       ├── tailwind.config.js
│       └── package.json
│
├── peer_server.py                   # [NEW]
├── demo_local.py                    # (không đổi)
├── demo_network.py                  # [NEW] optional auto-start script
│
├── tests/
│   ├── test_network_transport.py    # [NEW]
│   └── README_network_demo.md      # [NEW]
│
└── pyproject.toml                   # updated
```

---

## Execution Order (Tuần tự)

### Phase 4.1: Core Transport (~3h)
1. `network_transport.py` + unit tests
2. Install dependencies (fastapi, uvicorn, httpx)

### Phase 4.2: Peer Server (~3h)  
3. `peer_server.py` — CLI + all endpoints
4. Manual test: start 2 peers, send message via curl

### Phase 4.3: Dashboard Backend (~2h)
5. `dashboard_server.py` — aggregator + all endpoints
6. Test: start peers + dashboard, verify /api/ring-state

### Phase 4.4: Dashboard Frontend Foundation (~3h)
7. Vite + React + Tailwind setup
8. Layout shell (Header, MainGrid, PeerList, MetricsBar)  
9. `api.js` + `usePolling` + `useRingState` hooks
10. Basic state polling — hiển thị raw JSON

### Phase 4.5: Core Components (~5h)
11. `ChordRingViz` — SVG ring topology
12. `PeerCard` — full detail display
13. `QueryPanel` — input, results, routing trace display
14. `LogPanel` — message log with timestamps
15. `Controls` — setup buttons + churn controls

### Phase 4.6: Polish (~3h)
16. `MetricsBar` — aggregate stats
17. Ring topology highlights (routing path after query)
18. Integration test: full flow from setup → query → churn
19. Error states + loading states + empty states

---

## Tradeoffs

| Quyết định | Chọn | Bỏ | Lý do |
|---|---|---|---|
| Frontend | React + Tailwind v3 | Vanilla JS | User yêu cầu, component reuse tốt |
| Build tool | Vite | CRA, Next.js | Nhanh, đơn giản, không cần SSR |
| Data source | `p2p_library_100_stories.json` | Hardcoded PEER_DATA | Flexible, realistic |
| Design | Clean white/gray | Dark theme | User yêu cầu |
| Real-time | Polling 2s | WebSocket | Đủ cho demo, đơn giản |
| Ring viz | Vanilla SVG in React | D3.js | Ít dependency, kiểm soát hoàn toàn |
| HTTP client | httpx sync | httpx async / requests | Giữ nguyên sync Transport interface |

---

> [!IMPORTANT]
> **Xác nhận trước khi bắt đầu:**
> 1. Tailwind **v3** hay **v4**? (Đề xuất v3 — stable nhất)
> 2. Layout mockup ở trên có đúng ý bạn không? Cần điều chỉnh gì?

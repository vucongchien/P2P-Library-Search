# Plan: Tối ưu Dashboard Backend — Parallel Polling

## ✅ Checklist Tiến độ

| Task | File | Trạng thái |
|---|---|---|
| P1 — Đổi `PeerClient` từ sync sang async | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |
| P2 — Song song hóa `/api/peers` | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |
| P3 — Song song hóa `/api/ring-state` | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |
| P4 — Song song hóa `/api/metrics` | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |
| P5 — Song song hóa `/api/messages/all` | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |
| P6 — Giảm timeout xuống 1.0s | `dashboard/backend/dashboard_server.py` | ⬜ Chưa làm |

---

## 1. Vấn đề (Root Cause)

### Hiện tại: Sequential (Tuần tự)

```
Dashboard gọi N10 → [đợi] → gọi N60 → [đợi] → gọi N110 → [đợi] → ... gọi N210
```

Trong file `dashboard_server.py`, tất cả API aggregation đều dùng vòng `for` tuần tự với `httpx.get()` đồng bộ:

```python
# dashboard_server.py — HIỆN TẠI (Vấn đề)
for nid, client in peers.items():
    state = client.get("/api/state")  # Đợi từng node một!
```

`PeerClient` đang dùng `httpx.get()` **synchronous** với timeout **5.0 giây**.

### Hậu quả trong Demo

| Kịch bản | Thời gian bị đơ |
|---|---|
| 1 node chết | ~5 giây |
| 2 node chết cùng lúc | ~10 giây |
| 3 node chết cùng lúc | ~15 giây |

Đây là khoảng thời gian gây ấn tượng xấu nhất trong buổi thuyết trình: bạn vừa tắt node để demo self-healing nhưng Dashboard lại **đứng hình** trong nhiều giây.

**Trade-off khi sửa:**
- `+` Dashboard không bao giờ bị đơ, phản hồi luôn < 1.5s.
- `+` Node chết được phát hiện ngay lập tức.
- `-` Cần chuyển từ sync sang async (`async def` + `asyncio.gather`).
- `-` `PeerClient` phải dùng `httpx.AsyncClient` thay vì `httpx.get()`.

---

## 2. Mục tiêu

- **Thời gian phản hồi tối đa** của mỗi polling cycle: **≤ 1.5 giây** (kể cả khi có node chết).
- **Node chết** phải được Dashboard nhận biết và hiển thị "Offline" ngay trong vòng polling tiếp theo (2s).
- Dashboard **không bao giờ bị đơ** (blocking) trong lúc demo.

---

## 3. Tài liệu liên quan

| File | Vai trò |
|---|---|
| `docs/dashboard/auto_refresh_logic.md` | Mô tả workflow polling — cần sync sau khi sửa |
| `dashboard/backend/dashboard_server.py` | **Core** — nơi cần sửa |

---

## 4. Chi tiết cần làm

### Task P1 — Đổi `PeerClient` từ sync sang async

**File:** `dashboard/backend/dashboard_server.py`

Thay thế toàn bộ class `PeerClient`:

```python
# TRƯỚC (Sync — block)
class PeerClient:
    def get(self, path: str) -> Optional[dict]:
        r = httpx.get(f"{self.url}{path}", timeout=self.timeout)
        return r.json()

# SAU (Async — non-block)
class PeerClient:
    async def get(self, path: str) -> Optional[dict]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.url}{path}")
            return r.json()
```

Cũng giảm timeout mặc định từ `5.0` xuống `1.0` giây (Task P6).

---

### Task P2, P3, P4, P5 — Song song hóa các API

Đây là pattern áp dụng cho tất cả 4 endpoint:

```python
# TRƯỚC — Tuần tự, đơ khi node chết
@app.get("/api/ring-state")
def get_ring_state():
    for nid, client in peers.items():
        state = client.get("/api/state")  # Đợi từng node
        ...

# SAU — Song song, không bao giờ đơ
@app.get("/api/ring-state")
async def get_ring_state():
    # Tạo danh sách các "nhiệm vụ" cần chạy
    tasks = [client.get("/api/state") for client in peers.values()]
    
    # Chạy TẤT CẢ cùng lúc, mỗi task timeout riêng 1s
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Xử lý kết quả: skip nếu node nào lỗi
    states = {}
    for nid, result in zip(peers.keys(), results):
        if isinstance(result, dict):  # Thành công
            states[nid] = result
        else:  # Exception hoặc None → Node chết, skip
            warnings.append(f"Node {nid} unreachable")
    ...
```

**Thời gian thực tế:**
- Trước: `5 nodes × 5s timeout = 25s` (trường hợp xấu)
- Sau: `max(node response time) ≤ 1s` bất kể bao nhiêu node chết

---

## 5. Thứ tự triển khai

```
P6 (giảm timeout) → P1 (async PeerClient) → P2 → P3 → P4 → P5
```

Sau khi hoàn thành, cần cập nhật:
- `docs/dashboard/auto_refresh_logic.md`: Bổ sung cơ chế parallel polling.

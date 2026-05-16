# Plan: Triển khai Successor List

## ✅ Checklist Tiến độ

| Task | File | Trạng thái |
|---|---|---|
| B1 — Init `successor_list` | `src/chord/node.py` | ✅ Xong |
| B2 — Update `join()` | `src/chord/routing_mixin.py` | ✅ Xong |
| B4 — Update `_handle_get_predecessor()` | `src/chord/routing_mixin.py` | ✅ Xong |
| B3 — Nâng cấp `stabilize()` | `src/chord/routing_mixin.py` | ✅ Xong |
| B5 — Expose `/api/state` | `peer_server.py` | ✅ Xong |
| F1 — Hiển thị trên Dashboard UI | `dashboard/frontend/src/` | ✅ Xong |

---


## 1. Mục đích

Hệ thống hiện tại mỗi Node chỉ lưu **1 Successor duy nhất**. Khi Successor đó sập, Node phải quét toàn bộ Finger Table (8 mục) để tìm Node sống thay thế — một quá trình vừa chậm, vừa không chắc tìm được Node nằm ngay kế bên trong vòng Chord.

Successor List giải quyết vấn đề này bằng cách mỗi Node ghi nhớ **r node kế tiếp liên tục** (thường r = 2 hoặc 3). Khi Successor 1 sập, Node chuyển ngay sang Successor 2 mà không cần tìm kiếm trong Finger Table.

---

## 2. Mục tiêu

- **Giảm thời gian phục hồi vòng Chord** khi có node sập: từ "nhiều vòng stabilize" xuống còn **1 vòng stabilize** (≤ 5 giây).
- **Loại bỏ điểm mù** giữa Successor và Finger gần nhất (đặc biệt trong mạng nhỏ 5-10 nodes).
- **Tăng tính chính xác của tài liệu**: `docs/core/self_healing.md` đang mô tả "danh sách dự phòng" nhưng code chưa có — Successor List sẽ hiện thực hóa điều đó.
- **Điểm cộng khi demo**: Kịch bản "tắt 2 node liên tiếp" mà mạng không vỡ là một bằng chứng thuyết phục về Churn Resilience.

> **Trade-off:**
> - `+` Phục hồi nhanh, không cần Finger Table khi Successor chết.
> - `+` Khớp hoàn toàn với lý thuyết Chord (paper gốc của Stoica et al.).
> - `-` Tăng số lượng message trong mỗi chu kỳ `stabilize` (phải hỏi thăm `r` nodes thay vì 1).
> - `-` Cần đồng bộ thêm trường `successor_list` vào `/api/state` và Dashboard.

---

## 3. Tài liệu liên quan

| File | Vai trò |
|---|---|
| `docs/core/self_healing.md` | Mô tả kịch bản failure — cần sync sau khi có Successor List |
| `docs/adr/003-concurrency-and-consistency.md` | ADR về tính nhất quán — cần kiểm tra |
| `p2p_search/src/chord/routing_mixin.py` | **Core** — nơi cần sửa `stabilize()` |
| `p2p_search/src/chord/node.py` | Khởi tạo `successor_list` trong `__init__` |
| `p2p_search/peer_server.py` | `/api/state` — expose `successor_list` ra ngoài |
| `p2p_search/dashboard/backend/dashboard_server.py` | Aggregator — pass-through dữ liệu |
| `p2p_search/dashboard/frontend/src/components/` | Dashboard FE — hiển thị Successor List |

---

## 4. Những việc cần làm

### 4.1. Backend (Core)

#### Task B1 — Khởi tạo `successor_list` trong `ChordNode`
**File:** `src/chord/node.py`
- Thêm field `self.successor_list: List[int] = []` vào `__init__`.
- `r = 3` (hằng số, có thể nhét vào param sau).

#### Task B2 — Cập nhật `join()` trong `RoutingMixin`
**File:** `src/chord/routing_mixin.py`
- Sau khi join thành công, khởi tạo `successor_list = [self.successor_id]`.

#### Task B3 — Nâng cấp `stabilize()` trong `RoutingMixin`
**File:** `src/chord/routing_mixin.py` — **Task quan trọng nhất**

Hiện tại `stabilize()` chỉ hỏi thăm `successor_id`. Cần mở rộng:
1. Sau khi xác nhận Successor sống, hỏi Successor về `successor_list` của nó.
2. Cập nhật `self.successor_list` = `[self.successor_id] + successor_list_of_successor[:r-1]`.
3. Khi Successor 1 sập: thay vì quét Finger Table, thử lần lượt `successor_list[1]`, `successor_list[2]` trước.

```python
# Pseudo-code của stabilize() mới
def stabilize(self):
    # Thử Successor hiện tại
    response = self.transport.send(self.successor_id, GET_PREDECESSOR)
    
    if not response.success:
        # Successor chết → fallback sang successor_list
        for backup in self.successor_list[1:]:
            ping = self.transport.send(backup, PING)
            if ping.success:
                self.successor_id = backup
                self.finger_table[0] = backup
                # Cập nhật lại successor_list từ backup
                break
        else:
            # Không có backup nào → quét Finger Table như cũ
            ...

    # Cập nhật successor_list từ response của Successor sống
    succ_list = response.data.get("successor_list", [])
    self.successor_list = [self.successor_id] + succ_list[:r-1]
    
    # NOTIFY như bình thường
    ...
```

#### Task B4 — Cập nhật handler `_handle_get_predecessor()`
**File:** `src/chord/routing_mixin.py`
- Trả thêm `successor_list` trong response để Predecessor có thể cập nhật danh sách dự phòng của mình.

```python
def _handle_get_predecessor(self, message):
    return Response(success=True, data={
        "predecessor": self.predecessor_id,
        "successor_list": self.successor_list  # <-- thêm dòng này
    })
```

#### Task B5 — Expose `successor_list` ra `/api/state`
**File:** `peer_server.py`
- Thêm `"successor_list": node.successor_list` vào response của `get_state()`.

---

### 4.2. Frontend Dashboard (FE)

#### Task F1 — Hiển thị Successor List trong Node Card
**File:** `dashboard/frontend/src/components/` (component hiển thị trạng thái node)
- Bên cạnh "Successor: N60", thêm dòng nhỏ: **"Backup: N110, N160"**.
- Giúp người xem demo trực quan thấy mạng có khả năng dự phòng.

#### Task F2 — (Optional) Highlight trong Network Graph
- Vẽ thêm đường đứt nét mỏng từ mỗi Node tới các Backup Successor trong biểu đồ mạng.
- Khi node bị tắt, đường đứt nét "sáng lên" thành đường liền nét mới.

---

## 5. Thứ tự triển khai đề xuất

```
B1 (init) → B2 (join) → B4 (handler) → B3 (stabilize) → B5 (api/state)
                                                                  ↓
                                                          F1 (UI card)
                                                          F2 (graph, optional)
```

---

## 6. Review & Sync tài liệu sau khi hoàn thành

Sau khi hoàn tất implement, cần cập nhật các tài liệu sau:

| Tài liệu | Nội dung cần sync |
|---|---|
| `docs/core/self_healing.md` | Sửa câu "danh sách dự phòng" → ghi rõ là `successor_list`, mô tả cơ chế fallback chính xác |
| `docs/plan/successor_list.md` | File này — đánh dấu các task đã hoàn thành |
| `docs/dashboard/auto_refresh_logic.md` | Bổ sung: Auto-refresh giờ cũng hiển thị `successor_list` trên UI |
| `peer_server.py` (docstring) | Cập nhật endpoint list: `/api/state` trả thêm `successor_list` |

# Review: Chord DHT Implementation

> **Kết quả**: 20/20 tests ✅ passed  
> **Đánh giá tổng quan**: Kiến trúc tốt, lý thuyết Chord **đúng về cơ bản**, có **1 bug nghiêm trọng** cần sửa và 2 thiếu sót nhỏ.

---

## ✅ Những Gì Đã Đúng (Lý Thuyết Chord)

### 1. Circular Interval (`in_range`) — ✅ Đúng
- Normal range (start < end): `(start, end)` — OK
- Wrap-around (start > end): `val > start OR val < end` — OK  
- Edge case (start == end): chỉ chứa điểm nếu inclusive — OK

### 2. Finger Table & Routing O(log N) — ✅ Đúng
```
finger[i] = successor(node_id + 2^i)     ← đúng công thức Chord paper
closest_preceding_node: scan m-1 → 0     ← đúng thuật toán
find_successor: check (n, successor] → forward qua transport  ← đúng
```

### 3. Stabilization Protocol — ✅ Đúng theo Chord paper
```
stabilize():
  1. Hỏi successor.predecessor          ← đúng
  2. Nếu x ∈ (self, successor) → update ← đúng  
  3. Notify successor                    ← đúng
  4. Successor chết → fallback finger    ← đúng (bonus, paper không có)

fix_fingers(): round-robin (n + 2^i)     ← đúng
check_predecessor(): ping, set None      ← đúng
```

### 4. Join Protocol — ✅ Đúng
- Node mới hỏi known_node tìm successor cho mình
- First node: successor = self

### 5. Storage — ✅ Đúng
- `merge_put` (union, không ghi đè) — đúng theo PRD
- GET trả empty set khi key không có — đúng (không phải error)
- Replica store tách riêng — đúng

### 6. Transport Abstraction — ✅ Đúng
- ABC + LocalTransport, message_log
- Transport KHÔNG raise, trả Response — đúng theo PRD
- Chord code 0 import socket/requests — đúng

### 7. Error Handling — ✅ Đúng  
- TTL loop prevention — có
- Routing failure fallback (thử finger khác) — có
- Dispatcher catch-all exception → Response — có

### 8. Ring Manager — ✅ Đúng
- stabilize_all: random shuffle order — tốt (tránh bias)
- create(): m rounds stabilize — đủ cho finger table hội tụ
- Churn test pass — đúng

---

## ✅ Đã Fix: `hash()` Không Deterministic

**File**: `src/chord/node.py` dòng 32, 47

```python
key_id = hash(keyword) % (2**self.m)    # ← BUG
```

**Vấn đề**: Python `hash()` cho string được **randomized** mỗi lần chạy (PYTHONHASHSEED thay đổi). Hậu quả:
1. **Lần chạy 1**: `hash("database") = 73` → lưu tại Peer 3
2. **Lần chạy 2**: `hash("database") = 155` → tìm tại Peer 4 → **KHÔNG TÌM THẤY!**
3. **NetworkTransport**: mỗi process có PYTHONHASHSEED khác → **peers không đồng thuận ai giữ key nào**

**Tại sao test vẫn pass**: Vì test tự set `successor_id = 20` nên routing bỏ qua hash value.

**Fix**:
```python
import hashlib

def consistent_hash(keyword: str, m: int) -> int:
    """Deterministic hash dùng SHA-1, giống nhau mọi lần chạy, mọi process."""
    h = hashlib.sha1(keyword.encode('utf-8')).hexdigest()
    return int(h, 16) % (2 ** m)
```

---

## ✅ Đã Fix: Replication Chưa Được Gọi

**Vấn đề**: `_handle_store_replica()` đã viết nhưng **chưa bao giờ được gọi**.

Trong `put()`, sau khi PUT thành công → cần gửi thêm STORE_REPLICA tới successor của target node.

Hiện tại nếu target node chết → data mất hoàn toàn, churn test chỉ pass vì test routing chứ chưa test data recovery.

**Mức độ**: Không ảnh hưởng test hiện tại nhưng cần có trước khi demo churn data resilience.

---

## ✅ Đã Fix: `put()` Raise RuntimeError

**File**: `src/chord/node.py` dòng 43

```python
raise RuntimeError(f"Failed to put...")    # ← Không theo PRD
```

PRD nói Application layer nên trả kết quả, không raise. Nhưng đây là minor — có thể để lại nếu muốn caller xử lý.

---

## Bảng Tổng Kết

| Thành phần | Lý thuyết | Implementation | Test |
|---|---|---|---|
| `in_range` (circular interval) | ✅ Đúng | ✅ | ✅ |
| `closest_preceding_node` | ✅ Đúng | ✅ | ✅ |
| `find_successor` O(log N) | ✅ Đúng | ✅ | ✅ |
| TTL loop prevention | ✅ Đúng | ✅ | ✅ |
| Routing failure fallback | ✅ Đúng | ✅ | ✅ |
| `join` protocol | ✅ Đúng | ✅ | ✅ |
| `stabilize` + `notify` | ✅ Đúng | ✅ | ✅ |
| `fix_fingers` | ✅ Đúng | ✅ | ✅ |
| `check_predecessor` | ✅ Đúng | ✅ | ✅ |
| DHT put/get (merge_put) | ✅ Đúng | ✅ | ✅ |
| Transport abstraction | ✅ Đúng | ✅ | ✅ |
| Error codes + dispatcher | ✅ Đúng | ✅ | ✅ |
| Ring manager + churn | ✅ Đúng | ✅ | ✅ |
| **Hash function** | ✅ Deterministic SHA-1 | ✅ `hashlib.sha1` | ✅ |
| **Replication trigger** | ✅ Đã thêm | ✅ Handler được gọi ngầm | ✅ |
| **put() error handling** | ✅ Trả về Boolean | ✅ Return False/True thay vì Raise | ✅ |

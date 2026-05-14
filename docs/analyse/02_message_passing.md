# 02 — Message Passing (Implementation)

## Tiêu chí đề bài

> **Excellent**: Message passing hiệu quả (simulated **hoặc** real)
> **Satisfactory**: Hoạt động nhưng có thể chậm hoặc thiếu xử lý lỗi
> **Developing**: Message passing lỗi hoặc không tồn tại

## Verdict: **Excellent ✅**

Có **cả hai** mode: `LocalTransport` (simulated, in-process) và `NetworkTransport` (real HTTP/JSON, multi-process).

---

## Bằng chứng — Abstraction & 2 mode song song

| Thành phần | Vị trí | Vai trò |
| :--- | :--- | :--- |
| Interface `Transport` abstract | `src/transport.py::Transport` | Chord chỉ phụ thuộc interface, không biết bên dưới |
| `LocalTransport` (simulated) | `src/transport.py:40` | `registry: node_id → ChordNode`, send = function call |
| `NetworkTransport` (real) | `src/network_transport.py:24` | `registry: node_id → URL`, send = HTTP POST `/message` |
| FastAPI peer endpoint | `peer_server.py:131 /message` | Mỗi peer = 1 process độc lập, nhận message qua HTTP |
| Message dispatch tập trung | `chord/dispatcher_mixin.py::handle_message` | 11 message types route về handler tương ứng |
| Serialize/Deserialize JSON | `models/message.py::to_dict/from_dict`, `Response.to_dict/from_dict` | Đầy đủ cho cả 2 transport |

→ Cùng một bộ Chord logic chạy được cả trong test (Local) và demo thật (Network) mà không sửa code.

## Bằng chứng — Hiệu quả

| Yêu cầu | Cách giải quyết | Vị trí |
| :--- | :--- | :--- |
| Tránh overhead tạo TCP mỗi lần send | `httpx.Client` shared + connection pooling (max 50, keepalive 20) | `network_transport.py:42-59` |
| Timeout có giới hạn, không treo | `connect=5s`, `read=timeout_ms` truyền từ caller | `network_transport.py:96-107` |
| Sync interface → Chord logic không phải async-aware | `httpx.Client` (sync), không cần `asyncio` lan tỏa | `network_transport.py:38` |
| Cleanup connection pool | `atexit.register(_cleanup)` + `__exit__` | `network_transport.py:40, 177` |
| Log message metadata cho metrics | `Transport._log_message` ghi `from/to/type/timestamp` | `transport.py:30` |

## Bằng chứng — Error handling đầy đủ

`NetworkTransport.send()` map mọi lỗi mạng về `ErrorCode` chuẩn, **không bao giờ raise**:

| Tình huống | ErrorCode | Vị trí |
| :--- | :--- | :--- |
| Node không có trong registry | `NODE_NOT_FOUND` | `network_transport.py:82` |
| Connection refused / DNS fail | `NODE_UNREACHABLE` | `network_transport.py:145` |
| Read/connect timeout | `TIMEOUT` (kèm `timeout_ms`) | `network_transport.py:137` |
| HTTP 4xx/5xx | `NODE_UNREACHABLE` (kèm `http_status`) | `network_transport.py:111, 122` |
| Response JSON malformed | `NODE_UNREACHABLE` | `network_transport.py:162` |
| Handler exception ở peer nhận | `ROUTING_FAILED` (dispatcher) / `INTERNAL_ERROR` (server) | `dispatcher_mixin.py:34`, `peer_server.py:142` |

→ Chord logic chỉ cần check `response.success` và `response.error`, không phải try/except mạng.

## Bằng chứng — Test coverage

| Test file | Số test | Phạm vi |
| :--- | :--- | :--- |
| `tests/test_transport.py` | 4 | LocalTransport: send, registry, log, error path |
| `tests/test_network_transport.py` | 24 | NetworkTransport: HTTP success, 4xx/5xx, timeout, connect refused, JSON lỗi, pool lifecycle |

→ Bao phủ cả happy path lẫn mọi nhánh lỗi đã liệt kê.

## Điểm yếu nhỏ (không hạ điểm)

| Điểm | Mô tả | Tác động |
| :--- | :--- | :--- |
| HTTP/JSON, không phải binary protocol | Mỗi message ~vài trăm bytes overhead so với raw TCP | Chấp nhận được cho demo, debug dễ qua curl |
| Sync send → blocking khi peer chậm | Caller chờ tới khi response/timeout. Không có pipelining | OK ở scale demo (5-10 peers), không phải bottleneck thực tế |
| Không có retry tự động ở transport | Caller (Chord layer) phải tự retry qua `closest_preceding_node` fallback | Thực tế đã làm ở routing layer — tách trách nhiệm rõ ràng, không phải thiếu sót |
| Không TLS/auth | Trust mọi peer trong registry | Ngoài scope đề bài (P2P thuần) |

## Câu trả lời chuẩn cho thầy

**"Message passing simulated hay real?"** → **Cả hai.** `LocalTransport` cho unit test (function call, 1 process). `NetworkTransport` cho demo thật (HTTP POST, mỗi peer 1 FastAPI server, multi-process). Chord logic dùng chung interface `Transport`, đổi mode không cần sửa code.

**"Hiệu quả?"** → Connection pooling (httpx.Client shared), timeout có giới hạn, sync interface tránh phức tạp async, message log cho metrics. Sync HTTP là đủ ở scale 5-10 peers.

**"Xử lý lỗi?"** → 6 nhánh lỗi (registry miss, connection refused, timeout, HTTP 4xx/5xx, JSON malformed, handler exception) đều map về `ErrorCode` chuẩn. Transport **không bao giờ raise**, Chord chỉ cần check `response.success`.

**"Có test?"** → 28 test cho 2 transport (4 Local + 24 Network), bao phủ happy path và mọi nhánh lỗi.

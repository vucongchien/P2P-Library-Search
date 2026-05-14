# 03 — Analytical Metrics

## Tiêu chí đề bài

> **Excellent**: Có số liệu rõ: **Hops, Latency, Message Overhead**
> **Satisfactory**: Chỉ đếm số search thành công
> **Developing**: Không có dữ liệu định lượng

## Verdict: **🟡 Mostly Excellent — thiếu Latency**

---

## Đối chiếu 3 chỉ số bắt buộc

| Chỉ số | Trạng thái | Vị trí | Test |
| :--- | :--- | :--- | :--- |
| **Hops** | ✅ Đầy đủ | `RoutingTrace.hop_count`, `KeywordLookup.hops`, `QueryResult.total_hops`, `BatchMetrics.avg_hops_per_query` | `test_metrics::TestSnapshotCompare` |
| **Message Overhead** | ✅ Đầy đủ | `BatchMetrics.total_messages`, `messages_by_type`, `NodeTraffic.sent/received` (per node, per type) | `test_metrics::test_node_traffic_type_breakdown` |
| **Latency** | ❌ **THIẾU** | Không có field nào trong codebase đo wall-clock duration | — |

→ 2/3 đạt Excellent, 1/3 thiếu. **Không đủ để Excellent toàn phần.**

## Bằng chứng — Hops & Message Overhead

| Output | Code |
| :--- | :--- |
| Per query: `total_hops`, `total_messages`, `avg_hops_per_keyword` | `metrics.py::QueryStats` |
| Per node: `sent`, `received`, breakdown theo type | `metrics.py::NodeTraffic` |
| Toàn hệ thống: `total_messages`, `messages_by_type` | `metrics.py::BatchMetrics` |
| DHT health: `total_keys_in_dht`, `keys_distribution`, `replication_coverage` | `metrics.py::BatchMetrics` |
| Churn delta: `messages_delta`, `avg_hops_delta`, `keys_lost`, `keys_recovered_from_replica` | `metrics.py::ChurnDelta` |

→ Vượt yêu cầu Satisfactory ("chỉ đếm search thành công") rất xa.

## Vì sao thiếu Latency

1. `Transport._log_message` (`transport.py:30`) chỉ ghi `timestamp` lúc gọi `send()`. **Không ghi response time** → không tính được round-trip duration.
2. `RoutingHop` (`models/routing.py:14`) không có field timestamp hay duration_ms.
3. `metrics.py` không có hàm nào tính latency.

`grep latency|duration|elapsed` trong `src/metrics.py` → **0 match**.

## Fix Latency (~30 phút) để đạt Excellent

**Option 1 — Rẻ nhất:** Thêm `timestamp` vào `RoutingHop`:
```python
@dataclass
class RoutingHop:
    ...
    timestamp: float = field(default_factory=time.perf_counter)
```
→ Latency mỗi hop = `path[i+1].timestamp - path[i].timestamp`. Tổng latency query = `path[-1].timestamp - path[0].timestamp`.

**Option 2 — Đầy đủ hơn:** Đo round-trip ở `Transport.send()`:
```python
def send(self, to, msg, timeout_ms):
    t0 = perf_counter()
    response = self._do_send(...)
    response.latency_ms = (perf_counter() - t0) * 1000
    return response
```

→ Có latency cả request thành công lẫn thất bại (timeout).

**Bonus:** Thêm field `latency_ms` vào `QueryStats` + `BatchMetrics.avg_latency_per_query`.

## Câu trả lời chuẩn cho thầy

**"Có Hops?"** → Có. Per keyword, per query, average toàn hệ thống. Trace ghi từng hop với reason.

**"Có Message Overhead?"** → Có. Total, breakdown theo type (FIND_SUCCESSOR/PUT/GET/PING/...), per-node traffic, churn delta.

**"Có Latency?"** → **Chưa có**. Đây là điểm thiếu duy nhất so với mức Excellent.

**"Có dữ liệu định lượng?"** → Có. Vượt Satisfactory rõ ràng (`BatchMetrics`, `QueryStats`, `ChurnDelta` đều serialize được sang JSON, được test).

## Action item

- [ ] Thêm `timestamp: float` vào `RoutingHop` (~5 phút)
- [ ] Thêm `latency_ms` vào `QueryStats` (~10 phút)
- [ ] Update `metrics.py` để aggregate latency vào `BatchMetrics.avg_latency_per_query` (~15 phút)

→ Tổng ~30 phút để chuyển từ 🟡 Mostly Excellent sang ✅ Excellent toàn phần.

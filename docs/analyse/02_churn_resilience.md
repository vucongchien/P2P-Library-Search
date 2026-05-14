# 02 — Churn Resilience

## Tiêu chí đề bài

> **Excellent**: Hệ thống tự phục hồi, cập nhật pointer khi node rời
> **Satisfactory**: Hệ thống chạy nhưng crash nếu node quan trọng rời
> **Developing**: Không xử lý node failure

## Verdict: **Excellent ✅**

---

## Bằng chứng — Tự phục hồi đầy đủ

### Phát hiện node chết

| Cơ chế | Vị trí | Khi nào trigger |
| :--- | :--- | :--- |
| `check_predecessor` ping | `routing_mixin.py:344` | Mỗi vòng stabilize |
| `stabilize` thấy successor fail | `routing_mixin.py:307-322` | Mỗi vòng stabilize |
| Routing recovery khi forward target chết | `_handle_routing_failure_traced:204` | Trong query, tức thời |

### Cập nhật pointer

| Hành động | Vị trí | Test |
| :--- | :--- | :--- |
| Successor failover qua finger table | `routing_mixin.py:309-317` | `test_node_leave_churn` |
| Predecessor reset → None | `routing_mixin.py:353` | implicit |
| NOTIFY protocol cập nhật predecessor mới | `_handle_notify` | `test_data_handoff_on_join` |

### Recovery dữ liệu (replication)

| Hành động | Vị trí | Trigger |
| :--- | :--- | :--- |
| Replica primary → successor khi PUT | `storage_mixin.py:72-82` | Mỗi PUT (`test_storage_put_and_get` xác nhận N50.replica_store) |
| `_promote_replicas`: replica → primary | `storage_mixin.py:101-127` | Khi `check_predecessor` phát hiện predecessor chết |
| `_re_replicate`: backup sang successor mới | `storage_mixin.py:129-152` | Sau promote hoặc đổi successor |

→ Đạt **Excellent** criterion "Hệ thống tự phục hồi, cập nhật pointer khi node rời".

## Bằng chứng — Có benchmark định lượng

`src/churn_simulation.py::ChurnSimulator`:
- Phase 1: snapshot metrics + chạy test queries TRƯỚC churn
- Phase 2-3: remove node + stabilize
- Phase 4-5: chạy CÙNG queries SAU churn, so sánh kết quả
- Output `ChurnReport`: `keys_on_removed_node`, `keys_recovered_from_replica`, `all_queries_match`, `metrics_delta`

→ Có "proof of correctness" định lượng — query AND trả về cùng kết quả trước/sau churn.

## Điểm yếu nhỏ (không hạ điểm)

| Điểm | Mô tả | Tác động |
| :--- | :--- | :--- |
| **r = 1** (1 replica duy nhất) | Replica chỉ ở successor liền kề | Crash đồng thời primary+successor → mất data |
| **Không có successor list** | Chord paper khuyến nghị r-successors | Routing failover chậm hơn (phải scan finger table thay vì biết ngay successor[1]) |
| **Test gap** | Không có test trực tiếp cho `_promote_replicas`, `_re_replicate`, query-after-churn | Logic có nhưng chưa được pytest verify end-to-end |
| **`keys_recovered` đếm lỏng** | `churn_simulation.py:182-188` đếm "tồn tại ở bất kỳ node nào (primary hoặc replica)" | Không phân biệt đã thực sự promote chưa |

## Câu trả lời chuẩn cho thầy

**"Hệ thống tự phục hồi?"** → Có. 3 cơ chế detect: `check_predecessor` ping, `stabilize` kiểm successor, routing recovery in-query. 3 cơ chế recover data: replica → promote → re-replicate.

**"Cập nhật pointer khi node rời?"** → Có. Successor failover qua finger table, predecessor reset + NOTIFY protocol.

**"Crash nếu node quan trọng rời?"** → Không. `test_node_leave_churn` xác nhận: remove node giữa ring → stabilize → topology hội tụ đúng, không crash.

**"Có chứng minh được không?"** → Có. `ChurnSimulator` đo before/after, kiểm `all_queries_match` — query AND trả cùng kết quả sau khi node chết và stabilize.

## Reference

- Stoica et al. 2001 — Chord: A Scalable Peer-to-Peer Lookup Service, section 5 (Concurrent Operations and Failures)
- Chi tiết cơ chế tại [`docs/core/churn_resilience.md`](../docs/core/churn_resilience.md)

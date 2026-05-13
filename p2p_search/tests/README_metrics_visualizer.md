# Test Documentation: Metrics & Visualizer

## Tổng Quan

Module test cho 2 module Phase 3: `metrics.py` và `visualizer.py`.

## test_metrics.py

### Mục tiêu
Kiểm tra MetricsCollector phân tích **passive** từ `transport.message_log` và `ChordRing` state
mà KHÔNG sửa bất kỳ module core nào.

### Nhóm test

| # | Nhóm | Mô tả | Số test |
|---|---|---|---|
| 1 | Message Counting | Đếm total messages, phân loại by_type, slice log | 4 |
| 2 | Bandwidth Per Node | Sent/received per node, consistency check | 4 |
| 3 | Query Analysis | Phân tích QueryResult: hops, keywords, early_stop | 4 |
| 4 | DHT Health | Keys distribution, replication coverage, no-ring fallback | 3 |
| 5 | Report Generation | Tổng hợp BatchMetrics, to_dict, sorted traffic | 3 |
| 6 | Snapshot & Compare | Churn delta detection, query result matching | 6 |
| 7 | Edge Cases | Empty log, single node, reset | 3 |

### Chạy test
```bash
cd e:\LEARN\HTPT\p2p_search
uv run pytest tests/test_metrics.py -v
```

---

## test_visualizer.py

### Mục tiêu
Kiểm tra NetworkVisualizer tạo biểu đồ PNG đúng, không crash ở edge cases.

### Nhóm test

| # | Nhóm | Mô tả | Số test |
|---|---|---|---|
| 1 | Khởi tạo | Init với ring hợp lệ, ring 1 node | 2 |
| 2 | Ring Topology | Tạo PNG file, no fingers, custom title, 1 node | 4 |
| 3 | Query Path | Overlay routing path lên topology | 2 |
| 4 | DHT Distribution | Bar chart phân bổ keys | 2 |
| 5 | Churn Comparison | Highlight node đã chết, multi-node, actual remove | 3 |
| 6 | Edge Cases | Empty ring, auto create directory | 2 |

### Output
PNG files test được lưu tại: `results/graphs/test_output/`

### Chạy test
```bash
cd e:\LEARN\HTPT\p2p_search
uv run pytest tests/test_visualizer.py -v
```

---

## Chạy tất cả test
```bash
uv run pytest tests/ -v
```

# Walkthrough: Trung thực hóa Hệ thống Trace & Churn Simulation

## Tổng quan

Hệ thống Trace cũ mắc phải sai lầm thiết kế là dựng lại đường đi (reconstruct) bằng cách "đoán" từ `message_log`. Điều này dẫn đến sự thiếu chính xác và giả mạo dữ liệu routing.

Trong phiên này, chúng ta đã đập bỏ cơ chế cũ và **nhúng luồng Trace trực tiếp vào thuật toán Routing O(log N)**. Giờ đây, mỗi Node tự ghi lại hành động của chính mình và truyền cho Node tiếp theo. Đây là **Source of Truth** (Nguồn sự thật) chính xác 100%, bảo toàn thông tin ngay cả khi chuyển lên Network thật.

Đồng thời, dự án đã có module `churn_simulation.py` và script `demo_local.py` chạy từ A-Z.

## Các module đã thay đổi

| File quan trọng | Hành động | Mô tả |
|---|---|---|
| `src/models/routing.py` | NEW | Định nghĩa `RoutingHop` và `RoutingTrace`. |
| `src/chord/routing_mixin.py` | MODIFY | Sửa thuật toán để mỗi Node tích lũy path thực tế vào `response.data["path"]`. |
| `src/chord/node.py` | MODIFY | `get()` và `put()` trả thẳng `RoutingTrace` từ Transport. |
| `src/query_engine.py` | MODIFY | Xóa sạch logic "đoán mò" log. Đọc thẳng array trace từ Data response. Trang bị UI in log ASCII siêu chuẩn. |
| `src/metrics.py` | MODIFY | Tách thuộc tính `timestamp` và `type` vào `message_log` top-level phục vụ Metrics chuẩn. |
| `src/churn_simulation.py` | NEW | Module giả lập Test chịu lỗi bằng Benchmarks so sánh Query before/after. |
| `demo_local.py` | NEW | Script Pipeline: Setup Mạng ➔ Đẩy Index ➔ Query ➔ Trace ➔ Churn (Xóa Node) ➔ Vẽ Biểu Đồ ➔ Xuất file JSON. |

## Mẫu Routing Output (Mới)
Không những trung thực, Tracer giờ đây có thể xuất ra format cực chi tiết cho từng luồng O(log N).

```text
=======================================================
  Query: "system AND database" | Initiator: N10
  Status: SUCCESS | Result: HAS_RESULT
=======================================================
  Keyword: "system" (hash=154)
  |- [1] N10 --FORWARD--> N110  (closest_preceding_node -> N110)
  \- [2] N110 --RESOLVED--> N160  (key 154 ∈ (110, 160])
  \- GET N160 -> posting_list: {1, 2, 5, 10, 12, 40, 41}

  Keyword: "database" (hash=207)
  |- [1] N10 --FORWARD--> N160  (closest_preceding_node -> N160)
  \- [2] N160 --RESOLVED--> N210  (key 207 ∈ (160, 210])
  \- GET N210 -> posting_list: {1, 2, 3, 10, 30, 31}

  INTERSECT  {1, 2, 5, 10, 12, 40, 41} AND {1, 2, 3, 10, 30, 31} = {1, 2, 10}

  Final result: {1, 2, 10} (3 docs)
  Routing hops: 4 | Flags: {'early_stop': False, 'partial_data': False}
=======================================================
```

## Chạy thử nghiệm Demo

Để thấy mọi thứ hoạt động với Metrics + Graphing + Churn, vui lòng chạy lệnh:
```bash
uv run python demo_local.py
```

> [!TIP]
> **Production Readyness**
> Trace `RoutingHop` và `RoutingTrace` hiện tại đã được thiết kế dưới dạng Serializable (có cặp hàm `to_dict()` và `from_dict()`). Nhờ vậy, ở **Phase tiếp theo** khi chúng ta cắm `FastAPI` (NetworkTransport) vào thì Transport đi qua HTTP Response hoàn toàn không bị gãy format.

# 64. Distributed Inverted Index: "P2P Library Search"

## Dataset
- 100 text documents (Short Stories)

## Task
- Xây dựng một search engine dạng **P2P**
- Mỗi peer:
  - Index một tập con tài liệu
  - Lưu mapping: **Keyword → DocID** trong **DHT (Distributed Hash Table)**

## Analysis
- Thực hiện truy vấn nhiều từ khóa  
- Ví dụ: `"Distributed" AND "Database"`
- Trả về các tài liệu chứa **tất cả** từ khóa

## Deliverable
- Một bản trace cho thấy:
  - Những peer nào đã được contact
  - Trong quá trình resolve truy vấn AND

---

# Evaluation Criteria

| Criteria | Excellent | Satisfactory | Developing |
|----------|----------|--------------|------------|
| **Routing Logic** | Triển khai đúng DHT; xử lý được multi-hop paths | Routing cơ bản hoạt động nhưng có thể loop hoặc fail khi mạng lớn | Routing lỗi hoặc thực chất là centralized |
| **Churn Resilience** | Hệ thống tự phục hồi, cập nhật pointer khi node rời | Hệ thống chạy nhưng crash nếu node quan trọng rời | Không xử lý node failure |
| **Analytical Metrics** | Có số liệu rõ: Hops, Latency, Message Overhead | Chỉ đếm số search thành công | Không có dữ liệu định lượng |
| **Implementation** | Message passing hiệu quả (simulated hoặc real) | Code chậm, chỉ xử lý được N nhỏ | Không simulate được peer independence |

---

# Notes

- Có thể dùng Python với **NetworkX** để:
  - Vẽ topology mạng
  - Hiển thị đường đi của query
- Giúp bài demo trực quan và thuyết phục hơn
# BRD — Business Requirements Document
## Đề tài 64: Distributed Inverted Index — "P2P Library Search"

> **Phiên bản**: 1.0  
> **Ngày**: 2026-04-16  
> **Tác giả**: Sinh viên môn Hệ Thống Phân Tán

---

## 1. Bối Cảnh & Vấn Đề

### 1.1 Vấn đề của Search Engine truyền thống (Centralized)

```
        User A ──▶ ┌──────────┐
        User B ──▶ │  SERVER  │ ◀── Toàn bộ index + data
        User C ──▶ └──────────┘
                      ▲
                 Single Point of Failure
```

| Vấn đề | Mô tả |
|---|---|
| **SPOF** | Server chết = toàn bộ hệ thống chết |
| **Bottleneck** | Mọi query đều đi qua 1 server duy nhất |
| **Scaling cost** | Dữ liệu tăng → phải nâng cấp/mua thêm server |
| **Data sovereignty** | Toàn bộ tài liệu giao cho một thực thể duy nhất |

### 1.2 Giải pháp P2P

```
        Peer 0 ◀──────▶ Peer 1
          ▲    \       /   ▲
          │     \     /    │
          ▼      ▼   ▼    ▼
        Peer 4 ◀──▶ Peer 2
          ▲               ▲
          │               │
          ▼               ▼
               Peer 3

  Không có server trung tâm!
    Mỗi peer = vừa client + vừa server
    Bất kỳ peer nào cũng có thể khởi tạo query
    Peer chết → hệ thống vẫn chạy (no SPOF)
```

---

## 2. Mục Tiêu Đề Tài (Business Goals)

### 2.1 Mục tiêu chính

> **Xây dựng một search engine P2P dùng Chord DHT** để tìm kiếm tài liệu trên 100 short stories  
> phân tán trên nhiều peer, hỗ trợ truy vấn AND đa từ khóa, kèm bản trace rõ ràng.

### 2.2 Bảng mục tiêu cụ thể

| # | Mục tiêu | Ý nghĩa | Mức ưu tiên |
|---|---|---|---|
| G1 | **Distributed Indexing** | Mỗi peer index một tập con tài liệu, không ai giữ toàn bộ | 🔴 Bắt buộc |
| G2 | **DHT-based Routing** | Dùng Chord DHT để routing O(log N), không centralized | 🔴 Bắt buộc |
| G3 | **AND Query** | Hỗ trợ truy vấn nhiều từ khóa, trả về giao tập kết quả | 🔴 Bắt buộc |
| G4 | **Query Trace** | Ghi lại peer nào được contact, bao nhiêu hop, trong quá trình resolve | 🔴 Bắt buộc |
| G5 | **Churn Resilience** | Hệ thống tự phục hồi khi node join/leave | 🟡 Nên có |
| G6 | **Metrics** | Đo Hops, Latency, Message Overhead | 🟡 Nên có |
| G7 | **Visualization** | NetworkX vẽ topology + query path | 🟢 Nice to have |

---

## 3. Phạm Vi (Scope)

### 3.1 Trong phạm vi (In Scope)

| Hạng mục | Chi tiết |
|---|---|
| Dataset | 100 short stories, tiếng Anh, JSON format (id, title, category, content) |
| Kiến trúc | Simulated P2P — tất cả peers chạy trong cùng process Python |
| DHT | Chord protocol (ring, finger table, successor/predecessor) |
| Index | Distributed Inverted Index: keyword → Set[DocID] |
| Query | AND query resolution (sequential, trace từng bước) |
| Output | JSON trace, PNG topology graph |

### 3.2 Ngoài phạm vi (Out of Scope)

| Hạng mục | Lý do loại |
|---|---|
| Real network (socket/HTTP) | Quá phức tạp, không cần thiết cho học thuật |
| UI web interface | Scope là console + visualization |
| OR / NOT query | Chỉ cần AND theo đề bài |
| Ranking / TF-IDF | Chỉ cần boolean match, không cần xếp hạng |
| Persisting state trên disk | Simulated in-memory đủ rồi |
| Security / Authentication | Không thuộc scope distributed systems |

---

## 4. Stakeholders & Actors

| Actor | Vai trò | Giao tiếp với hệ thống |
|---|---|---|
| **User** | Người gõ query tìm kiếm | Gửi query string → nhận danh sách DocIDs |
| **Peer** | Một node trong mạng P2P | Lưu data + DHT store + phục vụ routing |
| **Initiator** | Peer nhận query từ User | Bất kỳ peer nào, không cố định |
| **Chord Ring** | Overlay network | Quản lý routing giữa các peer |

---

## 5. User Stories

### US-1: Distributed Index Build
> **Là** hệ thống  
> **Tôi muốn** tự động phân chia 100 tài liệu cho N peer, mỗi peer tự build inverted index rồi publish vào DHT  
> **Để** keyword nào cũng có thể tìm được từ bất kỳ peer nào

### US-2: AND Query
> **Là** người dùng  
> **Tôi muốn** gõ `"distributed AND database"` và nhận được danh sách tài liệu chứa CẢ HAI từ khóa  
> **Để** tìm được tài liệu chính xác nhất

### US-3: Query Trace
> **Là** người đánh giá (giáo viên)  
> **Tôi muốn** xem bản trace rõ ràng: peer nào đã được contact, bao nhiêu hop, theo thứ tự nào  
> **Để** đánh giá sinh viên hiểu cơ chế routing DHT

### US-4: Churn Handling
> **Là** hệ thống  
> **Tôi muốn** khi một peer rời mạng, các peer còn lại tự phát hiện và phục hồi  
> **Để** query vẫn trả kết quả đúng (có thể chậm hơn, nhưng không crash)

### US-5: Metrics Dashboard
> **Là** người phân tích  
> **Tôi muốn** xem các con số: tổng hops, tổng messages, latency  
> **Để** đánh giá hiệu suất routing và so sánh trước/sau churn

---

## 6. Tiêu Chí Đánh Giá (từ đề bài)

| Tiêu chí | Excellent 🎯 | Satisfactory | Developing |
|---|---|---|---|
| **Routing Logic** | DHT đúng, multi-hop routing | Routing cơ bản nhưng loop/fail | Centralized trá hình |
| **Churn Resilience** | Tự phục hồi khi node rời | Chạy nhưng crash nếu node quan trọng rời | Không xử lý |
| **Analytical Metrics** | Hops, Latency, Message Overhead rõ ràng | Chỉ đếm search thành công | Không có metric |
| **Implementation** | Message passing hiệu quả | Chậm, chỉ chạy N nhỏ | Không simulate peer independence |

### Mục tiêu của chúng ta: **Excellent ở cả 4 tiêu chí**.

---

## 7. Ràng Buộc (Constraints)

| Ràng buộc | Chi tiết |
|---|---|
| **Ngôn ngữ** | Python 3.10+ |
| **Thời gian** | ~2-3 tuần |
| **Platform** | Windows + PowerShell |
| **Dataset** | Đã có sẵn: `p2p_library_100_stories.json` |
| **Delivery** | Source code + Report + Demo (NetworkX visualization) |
| **Simulation** | In-process (không real network), nhưng phải thể hiện peer independence |

---

## 8. Giả Định (Assumptions)

1. **Dataset tiếng Anh** — không cần xử lý multi-language.
2. **Simulated P2P** — các peer là Python objects, message = function call. Đây là cách chuẩn trong học thuật.
3. **Số peer mặc định = 5** — đủ để demo Chord routing, có thể scale lên 10-20 để test.
4. **m = 8 bits** — ring size = 256, thừa sức cho 5-20 peer.
5. **User query từ console** — không cần web UI.
6. **Không cần stemming** — giữ nguyên từ gốc, dễ trace và debug.

---

## 9. Rủi Ro

| Rủi ro | Xác suất | Impact | Mitigation |
|---|---|---|---|
| Chord implementation sai routing | Cao | Toàn bộ hệ thống sai | Unit test routing riêng trước |
| Finger table stale sau churn | Trung bình | Query fail | Stabilize protocol + test |
| Index build merge sai (ghi đè thay vì union) | Trung bình | Query thiếu kết quả | Test merge_put cẩn thận |
| Dataset quá nhỏ → kết quả intersection luôn rỗng | Thấp | Demo không thuyết phục | Kiểm tra thống kê từ khóa trước |

---

## 10. Definition of Done

- [ ] 100 tài liệu được phân chia đều cho N peer
- [ ] Inverted index được build và publish vào DHT đúng
- [ ] AND query trả kết quả chính xác (verified against global index)
- [ ] Query trace output rõ ràng: peer path, hop count, messages
- [ ] Hệ thống chạy được sau khi 1 peer rời mạng (churn)
- [ ] Metrics: Hops, Latency, Message Overhead được ghi log
- [ ] NetworkX visualization cho topology + query path
- [ ] Tất cả unit tests pass
- [ ] Report báo cáo hoàn chỉnh

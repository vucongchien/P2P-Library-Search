# ADR 001: Distributed Query Strategy for Multi-keyword search

- **Status**: Accepted
- **Decider**: Team & AI Assistant
- **Date**: 2026-05-13

## 1. Context and Problem Statement

Trong hệ thống P2P Library Search, chúng ta cần hỗ trợ truy vấn đa từ khóa (Multi-keyword) kết hợp bằng toán tử `AND`. Do chỉ mục ngược (Inverted Index) được phân tán trên nhiều node khác nhau trong mạng Chord DHT, việc lấy dữ liệu và thực hiện phép giao (Intersection) đòi hỏi một chiến lược định tuyến và xử lý hiệu quả.

Câu hỏi đặt ra là: Thực hiện phép giao ở đâu? Lấy dữ liệu theo thứ tự nào? Và làm sao để giảm thiểu tối đa số lượng thông điệp (messages) trao đổi trên mạng?

## 2. Decision Drivers

- **Network Overhead**: Cần giảm số lượng Hops và Messages để hệ thống không bị nghẽn (Bottleneck).
- **Simplicity**: Thuật toán cần dễ hiểu, dễ debug và dễ cài đặt trong môi trường phân tán.
- **Accuracy**: Đảm bảo kết quả cuối cùng là giao chính xác của tất cả các tập posting list.
- **Performance**: Cân bằng giữa độ trễ (Latency) và băng thông (Bandwidth).

## 3. Considered Options

1.  **Parallel Fetch & Join at Initiator**: Initiator gửi đồng thời các yêu cầu GET cho mọi từ khóa trong truy vấn.
2.  **Distributed Join (Pipeline)**: Truy vấn được chuyển tiếp theo chuỗi `Initiator -> Node A -> Node B -> Node C -> Initiator`. Mỗi node thực hiện phép giao cục bộ rồi chuyển kết quả cho node tiếp theo.
3.  **Sequential Fetch & Incremental Intersection at Initiator** (Lựa chọn hiện tại): Initiator fetch từng từ khóa một, thực hiện phép giao ngay lập tức và quyết định có tiếp tục hay không.

## 4. Decision Outcome

Chúng tôi chọn **Option 3: Sequential Fetch & Incremental Intersection at Initiator**.

### Tại sao không chọn Option 1 (Parallel Fetch)?
- **Thiếu cơ chế Early Stop**: Parallel fetch buộc phải gửi mọi yêu cầu đi cùng lúc. Ngay cả khi từ khóa đầu tiên không có kết quả, các yêu cầu cho từ khóa sau đã "bay" trên mạng, gây lãng phí băng thông cực lớn trong hệ thống P2P.
- **Network Burst**: Gây áp lực lên băng thông của Initiator tại một thời điểm (Micro-burst), đặc biệt khi danh sách từ khóa dài.

### Tại sao không chọn Option 2 (Distributed Join)?
- **Mất quyền kiểm soát (Loss of Control)**: Initiator chỉ gửi đi và đợi ở cuối. Nếu chuỗi bị đứt ở giữa do lỗi node (Churn), Initiator không biết chính xác lỗi ở đâu để khắc phục hoặc báo cáo.
- **Dữ liệu phình to (Packet Bloat)**: Thông điệp di chuyển trong chuỗi phải cõng theo cả tập kết quả trung gian ngày càng lớn, gây gánh nặng cho các node trung gian thay vì dồn về Initiator (nơi thường có tài nguyên tốt hơn).
- **Phức tạp hóa Node logic**: Mỗi node Chord phải gánh thêm logic xử lý truy vấn phức tạp thay vì chỉ làm nhiệm vụ lưu trữ/định tuyến thuần túy.

### Tại sao chọn Option 3 (Sequential)?
- **Tối ưu hóa Early Stop**: Đây là lợi thế tuyệt đối. Nếu tập giao rỗng tại bất kỳ bước nào, chúng ta dừng ngay, tiết kiệm hàng chục thông điệp mạng.
- **Tính tin cậy**: Initiator làm "nhà điều phối", nắm bắt được trạng thái của từng từ khóa. Nếu node chứa từ khóa B chết, hệ thống vẫn giữ được kết quả của từ khóa A (Partial Result).
- **Khả năng Tracing**: Dễ dàng thu thập "Source of Truth" cho từng từ khóa để phục vụ báo cáo đồ án.

## 5. Pros and Cons of the Selected Option

### Pros:
- **Tiết kiệm băng thông nhất**: Nhờ cơ chế Early Stop khi gặp kết quả rỗng.
- **Dễ debug**: Logic tập trung tại một chỗ (QueryEngine tại Initiator).
- **Resource friendly**: Initiator kiểm soát được tốc độ truy vấn, không gây dồn ứ message trên mạng cùng lúc.

### Cons:
- **Latency cao hơn**: Tổng thời gian phản hồi là $\sum \text{Latency}(Keyword_i)$ thay vì $\max \text{Latency}(Keyword_i)$.
- **Phụ thuộc vào Initiator**: Node khởi tạo phải gánh vác việc tính toán phép giao (tuy nhiên phép giao các tập ID doc thường không tốn quá nhiều CPU).

## 6. Consequences

- Hệ thống sẽ ưu tiên tính "Network-friendly" (tiết kiệm hop mạng) hơn là tốc độ phản hồi tức thì.
- Trong tương lai, nếu tập dữ liệu cực lớn, có thể cân nhắc sắp xếp các từ khóa theo độ hiếm (Rareness) trước khi fetch để tối ưu hóa khả năng Early Stop.

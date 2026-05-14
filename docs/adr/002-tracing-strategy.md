# ADR 002: Tracing Strategy for P2P Routing

- **Status**: Accepted
- **Decider**: Team & AI Assistant
- **Date**: 2026-05-13

## 1. Context and Problem Statement

Để phục vụ việc báo cáo đồ án và đánh giá hiệu năng thuật toán Chord DHT, hệ thống cần một cơ chế ghi vết (Tracing) chính xác. Chúng ta cần biết thông điệp đã đi qua những node nào, tổng số Hops thực tế là bao nhiêu và lý do định tuyến tại mỗi chặng.

Thử thách: Làm sao để có Trace chính xác mà không làm tăng đáng kể Overhead mạng hoặc độ phức tạp của hệ thống?

## 2. Decision Drivers

- **Accuracy (Source of Truth)**: Trace phải được ghi lại bởi chính node thực hiện định tuyến, không phải suy luận từ log.
- **Observability**: Initiator phải nhận được Trace ngay khi có kết quả để hiển thị lên dashboard.
- **Reliability**: Trace không được bị mất khi có một phần mạng bị lỗi.
- **Low Overhead**: Không sử dụng quá nhiều message phụ chỉ để phục vụ tracing.

## 3. Considered Options

1.  **Log-based Reconstruction**: Mỗi node ghi log cục bộ, sau đó thu thập tất cả log về để dựng lại đường đi.
2.  **Event-driven Tracing (Out-of-band)**: Mỗi hop phát ra một sự kiện (Event/UDP) gửi về một trung tâm giám sát.
3.  **In-band Request-Response Tracing (Lựa chọn hiện tại)**: Thông tin trace "đi nhờ" trong chính thông điệp yêu cầu và phản hồi.

## 4. Decision Outcome

Chúng tôi chọn **Option 3: In-band Request-Response Tracing**.

### Cơ chế hoạt động:
- Khi một yêu cầu di chuyển qua các node, mỗi node trung gian sẽ đính kèm thông tin của mình (ID, Next Hop, Reason) vào một danh sách `routing_trace` nằm trong Payload của thông điệp.
- Khi thông điệp tới đích, node đích gửi toàn bộ danh sách này về cho Initiator trong gói tin phản hồi (Response).

### Tại sao không chọn Option 1 (Log-based)?
- **Thiếu tính thời thực**: Không thể hiển thị trace ngay lập tức trên UI.
- **Khó khớp nối**: Việc đồng bộ thời gian (Clock synchronization) giữa các node để sắp xếp log là cực kỳ khó khăn trong hệ thống phân tán.

### Tại sao không chọn Option 2 (Event-driven)?
- **Overhead cao**: Gấp đôi số lượng message trên mạng (mỗi hop tốn 1 message dữ liệu + 1 message event).
- **Vấn đề "Điểm mù"**: Nếu Initiator dùng phương pháp Pipeline (ADR 001), việc mất gói tin dữ liệu sẽ dẫn đến việc mất luôn ngữ cảnh của các event đã gửi trước đó.

### Lý do chọn Option 3 (In-band):
- **Chính xác tuyệt đối**: Mỗi node tự ghi lại hành động của mình ngay tại thời điểm thực hiện (Source of Truth).
- **Zero extra messages**: Không tốn thêm bất kỳ message nào, trace chỉ là một mảng nhỏ đính kèm trong payload.
- **Dễ debug**: Nếu nhận được kết quả, chắc chắn có trace. Nếu không có kết quả, Initiator vẫn biết được trace của các từ khóa trước đó (trong mô hình Sequential Fetch).

## 5. So sánh: Forward Tracing vs. Return Tracing (Lựa chọn hiện tại)

Chúng tôi đã cân nhắc việc đính kèm Trace ngay từ lúc gửi yêu cầu (Chiều đi), nhưng cuối cùng chọn cách tích lũy khi trả về (Chiều về).

| Đặc điểm | Forward Tracing (Chiều đi) | Return Tracing (Chiều về - Đang chọn) |
| :--- | :--- | :--- |
| **Băng thông** | **Tốn hơn**: Request payload phình to dần qua từng chặng. | **Tối ưu**: Request luôn nhỏ gọn. Chỉ có Response mang dữ liệu trace. |
| **Tính sẵn sàng** | Tốt hơn: Nếu node cuối chết, node trước đó vẫn có một phần trace. | Kém hơn: Nếu node cuối chết, toàn bộ trace của chuỗi đó bị mất. |
| **Độ phức tạp code** | Trung bình: Phải truyền mảng trace qua mọi API. | Thấp: Tận dụng cơ chế đệ quy (Stack) tự nhiên của hàm. |
| **Logic Early Stop** | Không hỗ trợ tốt: Dữ liệu vẫn phải đi tiếp để mang trace. | **Hỗ trợ tuyệt vời**: Nếu rỗng, dừng ngay, không cần trả về trace vô ích. |

## 6. Pros and Cons

### Pros:
- Đơn giản, không cần hạ tầng giám sát riêng (như Jaeger/Zipkin).
- Phản ánh đúng thực tế 100% đường đi của gói tin.
- Dễ dàng tích hợp vào Visualization (vẽ đồ thị ring và đường đi).
- **Network-efficient**: Giữ cho các gói tin "đi tìm" (Request) luôn đạt tốc độ cao nhất vì kích thước tối thiểu.

### Cons:
- Làm tăng kích thước gói tin phản hồi (Response).
- Nếu node đích chết đột ngột trước khi kịp gửi Response, phần trace từ initiator đến node sát đích sẽ bị mất.

## 7. Consequences

- Hệ thống Visualization sẽ dựa hoàn toàn vào mảng `routing_trace` trả về để vẽ đồ thị.
- Mọi node trong hệ thống phải tuân thủ việc cập nhật mảng trace này trong logic định tuyến.

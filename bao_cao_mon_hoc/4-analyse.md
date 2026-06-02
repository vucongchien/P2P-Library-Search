# DESIGN JUSTIFICATION REPORT
## Distributed Inverted Index: P2P Library Search
### Phân tích Bài toán và Biện minh Thiết kế theo Lý thuyết Cơ sở Dữ liệu Phân tán

> **Khung lý thuyết tham chiếu**: M. Tamer Özsu & Patrick Valduriez, *Principles of Distributed Database Systems* (4th ed.)
> **Phạm vi đề tài**: P2P Search Engine — Distributed Inverted Index — DHT — Multi-keyword AND Query — Trace Routing Path

---

## 1. PHÂN TÍCH BÀI TOÁN (Problem Analysis)

### 1.1 Bài toán gốc và các ràng buộc cốt lõi

Đề tài yêu cầu xây dựng một **hệ thống tìm kiếm tài liệu phân tán ngang hàng (P2P)**, trong đó:

- Dữ liệu (100 tài liệu dạng văn bản ngắn) được **phân tán** trên nhiều peer, không tập trung tại một node duy nhất.
- Người dùng có thể **tìm kiếm bằng nhiều từ khóa (AND query)** từ bất kỳ peer nào.
- Hệ thống phải **trace rõ đường định tuyến** (peer nào được liên hệ, bao nhiêu hop).
- Cơ chế lưu trữ chỉ mục phải **phân tán theo nguyên lý DHT**.

Không có yêu cầu nào của đề bài chỉ định rằng Chord là giải pháp bắt buộc. Chord là một **lựa chọn kỹ thuật** để hiện thực DHT — và lựa chọn này cần được biện minh dựa trên phân tích bài toán.

### 1.2 Ba bài toán phân tán cốt lõi cần giải quyết

Phân tích yêu cầu đề tài cho thấy có ba bài toán phân tán độc lập nhưng liên kết chặt chẽ:

**Bài toán 1 — Distributed Data Placement:**
Làm thế nào để phân chia 100 tài liệu lên N peer sao cho: (a) không node nào giữ toàn bộ dữ liệu, (b) dữ liệu phân bố đều, tránh hot-spot, (c) khi thêm/bớt node thì chi phí tái phân bổ là tối thiểu?

**Bài toán 2 — Distributed Inverted Index:**
Inverted index ánh xạ `keyword → Set[DocID]`. Trong môi trường phân tán, cần quyết định: index này được lưu ở đâu? Node nào chịu trách nhiệm quản lý mỗi entry? Làm sao đảm bảo lookup chính xác mà không cần catalog tập trung?

**Bài toán 3 — Distributed Lookup & Query Processing:**
Khi người dùng gõ truy vấn `"A AND B AND C"`, hệ thống phải định tuyến đến đúng các node chứa chỉ mục của A, B, C; thu thập posting lists; tính giao tập; và trả kết quả — tất cả mà không có một coordinator trung tâm.

---

## 2. PHÂN TÍCH CÁC PHƯƠNG ÁN THIẾT KẾ (Design Alternatives)

Trước khi lựa chọn Chord DHT, cần đánh giá các phương án kiến trúc khác nhau dựa trên các tiêu chí của Özsu & Valduriez: **Autonomy**, **Query Expressiveness**, **Routing Efficiency**, **Fault Tolerance**.

### 2.1 Phương án 1: Centralized Index (Chỉ mục tập trung)

Một server trung tâm lưu toàn bộ inverted index. Các peer lưu tài liệu và gửi index lên server khi có dữ liệu mới.

**Ưu điểm**: Lookup O(1), AND query đơn giản, dễ cài đặt.

**Nhược điểm**:
- Vi phạm yêu cầu "phân tán" của đề bài.
- Single Point of Failure (SPOF): server chết, toàn bộ tìm kiếm ngừng.
- Bottleneck hiệu năng khi số peer tăng.
- Không thể trace routing path qua DHT (không đáp ứng yêu cầu G4 của BRD).

**Loại bỏ vì**: Mâu thuẫn trực tiếp với yêu cầu P2P và DHT của đề bài.

### 2.2 Phương án 2: Super-peer Hybrid

Một số peer được chọn làm "siêu nút" (super-peer) quản lý chỉ mục cho một nhóm peer thường.

**Ưu điểm**: Giảm overhead định tuyến so với Flooding, hỗ trợ query phức tạp tại super-peer.

**Nhược điểm**:
- Super-peer là điểm lỗi cục bộ (partial SPOF): khi super-peer sập, toàn bộ nhóm peer thường mất khả năng tìm kiếm.
- Cần cơ chế bầu chọn super-peer, tăng độ phức tạp hệ thống.
- Phân bổ tải không đồng đều theo bản chất thiết kế.
- Không phù hợp với quy mô nhỏ (8-10 node) của đề tài — lợi ích của super-peer chỉ rõ rệt khi mạng có hàng ngàn node.

**Loại bỏ vì**: Vẫn tạo điểm lỗi cục bộ; overhead bầu chọn super-peer không phù hợp với quy mô bài toán.

### 2.3 Phương án 3: Unstructured P2P (Flooding / Random Walk)

Không có cấu trúc định tuyến cố định. Khi cần tìm kiếm, node khởi tạo broadcast yêu cầu đến tất cả peer trong phạm vi TTL.

**Ưu điểm**: Tính tự trị cao, không cần duy trì cấu trúc định tuyến, hỗ trợ keyword search tự nhiên.

**Nhược điểm**:
- Chi phí thông điệp tăng theo hàm mũ: $O(d^{TTL})$ với $d$ là số peer kết nối trung bình.
- Không đảm bảo tìm thấy dữ liệu nếu TTL không đủ lớn (probabilistic lookup, not guaranteed).
- Không thể trace routing path có ý nghĩa (yêu cầu G4 của BRD không đáp ứng đầy đủ).
- Tạo network congestion khi số peer tăng — không scalable.

**Loại bỏ vì**: Không đáp ứng yêu cầu trace routing DHT và không scalable theo định nghĩa của đề bài.

### 2.4 Phương án 4: Structured P2P — DHT

DHT (Distributed Hash Table) cung cấp cấu trúc định tuyến xác định: mỗi key được ánh xạ đến đúng một node chịu trách nhiệm thông qua hàm băm. Các hiện thực phổ biến gồm Chord, Kademlia, Pastry, CAN.

**Ưu điểm chung**:
- Lookup có chi phí xác định (deterministic), không phụ thuộc vào luck hay TTL.
- Phân bổ dữ liệu đồng đều theo consistent hashing.
- Có thể trace routing path rõ ràng (đáp ứng G4 của BRD).

**Nhược điểm chung**:
- Chỉ hỗ trợ exact-match lookup theo key — keyword search cần lớp chỉ mục bổ sung.
- Cần duy trì cấu trúc định tuyến (finger table, successor list...) — overhead khi có churn.
- Eventual consistency: cấu trúc định tuyến có thể tạm thời không nhất quán sau khi node join/leave.

**Chọn phương án này** vì phù hợp trực tiếp với yêu cầu "DHT-based Routing" (G2 của BRD) và cho phép trace path có ý nghĩa.

---

## 3. QUYẾT ĐỊNH THIẾT KẾ (Design Decisions)

### 3.1 Lựa chọn hiện thực DHT: Tại sao Chord?

Sau khi xác định DHT là phương án phù hợp, câu hỏi tiếp theo là: **chọn hiện thực DHT nào?** Các ứng viên gồm Chord, Kademlia, Pastry, CAN.

#### So sánh các hiện thực DHT

| Tiêu chí | Chord | Kademlia | Pastry | CAN |
|:---|:---|:---|:---|:---|
| **Topology** | Ring 1 chiều | XOR metric space | Prefix routing | d-dimensional torus |
| **Routing cost** | $O(\log N)$ hops | $O(\log N)$ hops | $O(\log N)$ hops | $O(d \cdot N^{1/d})$ hops |
| **Finger table size** | $O(\log N)$ entries | $O(\log N)$ entries | $O(\log N)$ entries | $O(d)$ entries |
| **Churn handling** | Stabilization protocol | Routing table refresh | Periodic updates | Zone split/merge — phức tạp |
| **Độ phức tạp cài đặt** | Thấp — ring đơn giản | Trung bình — XOR distance | Cao — prefix table | Cao — zone management |
| **Khả năng chứng minh tính đúng** | Có — bài báo gốc có proof | Có — nhưng XOR metric khó hình dung | Có | Có nhưng churn phức tạp |

#### Lý do chọn Chord

**Lý do chính (academic, không phải marketing)**:

1. **Cấu trúc ring cho phép chứng minh tính đúng đắn một cách trực tiếp**: Chord định nghĩa rõ ràng `successor(k)` — node có ID nhỏ nhất lớn hơn hoặc bằng $k$ trong không gian vòng — làm cơ sở xác minh tính Completeness và Disjointness của phân mảnh dữ liệu (xem Mục 3.3). Với Kademlia, việc chứng minh tương đương khó hơn do metric XOR không trực quan.

2. **Finger table với $O(\log N)$ entries có độ phức tạp phân tích rõ ràng**: Mỗi entry $i$ của finger table trỏ đến `successor(n + 2^{i-1})`. Chi phí lookup có thể chứng minh toán học là $O(\log N)$ hops expected. Điều này quan trọng cho yêu cầu trace routing (G4 của BRD) — mỗi hop trong trace có ý nghĩa cụ thể trong thuật toán.

3. **Phù hợp với quy mô bài toán (8-10 node, m=8 bits)**: Với N nhỏ, finger table của Chord có tối đa 8 entries ($m=8$), manageable và dễ kiểm tra đúng sai trong unit test. CAN sẽ cần quản lý zone phức tạp hơn khi node join/leave.

**Chi phí và hạn chế của Chord cần thừa nhận**:

- **Chi phí duy trì finger table**: Khi có churn (node join/leave), các finger table có thể trỏ đến node đã sập. Thuật toán `fix_fingers` cần chạy định kỳ để làm mới, tốn thêm $O(\log N)$ thông điệp mạng mỗi chu kỳ.
- **Chi phí Stabilization**: Tiến trình `stabilize` và `check_predecessor` cần giao tiếp với successor và predecessor định kỳ. Trong môi trường churn cao, overhead của các thông điệp stabilization có thể vượt qua overhead của các thông điệp query.
- **Eventual Consistency của routing**: Sau khi một node join hoặc leave, cấu trúc ring chỉ đạt trạng thái nhất quán *dần dần* qua nhiều chu kỳ stabilization. Trong khoảng thời gian chuyển tiếp này, một lookup có thể định tuyến đến node không đúng (stale finger table).
- **Churn impact lên O(log N) bound**: Bound $O(\log N)$ hop chỉ đúng khi finger table nhất quán. Trong thực tế với churn cao, số hop thực tế có thể vượt $O(\log N)$ do phải fallback về successor chaining.
- **Replica management complexity**: Khi node join, dữ liệu từ successor cần được tái phân bổ một phần sang node mới. Khi node leave, replica cần được promote. Hai tiến trình này cần phối hợp cẩn thận để tránh data loss trong khoảng thời gian chuyển tiếp.

**Kết luận lựa chọn Chord**: Trong bối cảnh bài toán có quy mô nhỏ (8-10 node), yêu cầu trace routing rõ ràng, và ưu tiên khả năng chứng minh tính đúng đắn trong báo cáo học thuật, Chord là lựa chọn phù hợp hơn Kademlia (XOR khó hình dung) và CAN (zone management phức tạp). Chord không phải là lựa chọn tối ưu tuyệt đối trong mọi trường hợp, nhưng phù hợp với ràng buộc cụ thể của đề tài này.

---

### 3.2 Consistent Hashing và Phân mảnh Ngang

Chord sử dụng **Consistent Hashing** (băm nhất quán) để giải quyết Bài toán 1 (Data Placement). Cụ thể:

- Cả node ID và key ID đều được ánh xạ vào không gian vòng $[0, 2^m - 1]$ bằng SHA-1.
- Mỗi key $k$ được quản lý bởi `successor(k)` — node có ID nhỏ nhất $\geq k$ trong vòng.
- Khi một node join hoặc leave, chỉ dữ liệu của node kề cạnh bị di chuyển — không cần tái phân bổ toàn bộ.

**Tại sao Consistent Hashing tốt hơn Static Hashing cho bài toán này?**

Với static hashing (`node = key % N`), khi N thay đổi (node join/leave), gần như toàn bộ dữ liệu phải được tái phân bổ. Consistent hashing giới hạn chi phí tái phân bổ ở mức $O(K/N)$ keys trung bình, với $K$ là tổng số key. Đây là thuộc tính quan trọng cho môi trường P2P có churn.

**Lưu ý về phân phối đồng đều**: SHA-1 cung cấp phân phối xấp xỉ đồng đều trên không gian key, nhưng với số node nhỏ (N=8-10), sự chênh lệch tải giữa các node có thể đáng kể do yếu tố ngẫu nhiên. Việc sử dụng virtual nodes (như trong Dynamo) có thể cải thiện cân bằng tải, nhưng nằm ngoài phạm vi đề tài.

---

### 3.3 Phân mảnh Ngang và Tính đúng đắn theo Özsu & Valduriez

Özsu & Valduriez (Chương 3) định nghĩa một phân mảnh ngang đúng đắn khi thỏa mãn ba điều kiện: **Completeness**, **Reconstruction**, **Disjointness**.

Hệ thống sử dụng Consistent Hashing của Chord để hiện thực phân mảnh ngang (Horizontal Fragmentation - PHF) trên tập tài liệu và inverted index. Dưới đây là đánh giá mức độ đáp ứng:

#### 3.3.1 Completeness (Tính đầy đủ)

*Định nghĩa (Özsu & Valduriez)*: Với mỗi tuple $t \in R$, phải tồn tại ít nhất một mảnh $R_i$ sao cho $t \in R_i$.

*Đánh giá*: Không gian khóa Chord là vòng đóng $[0, 2^m - 1]$. Với $m = 8$, không gian gồm 256 giá trị nguyên. Hàm `deterministic_hash(key, m)` là hàm toàn phần (total function): với mọi đầu vào, hàm luôn trả về một giá trị trong $[0, 255]$.

*Tuy nhiên, cần phân biệt hai mức Completeness*:

- **Hash completeness** (hàm băm luôn trả về giá trị): Đúng theo định nghĩa hàm toàn phần.
- **Routing completeness** (lookup luôn tìm đến đúng node chịu trách nhiệm): Chỉ đúng **dưới giả định finger table nhất quán**. Nếu finger table stale sau churn, lookup có thể không định tuyến đến đúng `successor(k)`.

*Kết luận*: Completeness được đảm bảo ở mức cấu trúc (hash space là đóng), nhưng **không tuyệt đối ở mức runtime** trong điều kiện churn. Câu nói "SHA-1 luôn ánh xạ vào một node" chỉ chứng minh hash completeness, không đủ để chứng minh routing completeness theo nghĩa đầy đủ của Özsu & Valduriez.

#### 3.3.2 Reconstruction (Tính tái dựng)

*Định nghĩa*: Phải tồn tại toán tử $\nabla$ sao cho $R = \nabla_{i}(R_i)$. Với PHF, toán tử này là UNION.

*Chứng minh*: Tập hợp tất cả tài liệu trong hệ thống có thể tái dựng bằng:
$$R = \bigcup_{i=1}^{N} \text{content\_store}(\text{Node}_i)$$

Điều kiện: mỗi tài liệu tồn tại trong đúng một primary node (xem Disjointness bên dưới), và tất cả node đang hoạt động. Khi có replica, reconstruction vẫn đúng vì replica là bản sao, không phải mảnh khác nhau.

#### 3.3.3 Disjointness (Tính tách biệt)

*Định nghĩa*: Nếu $t \in R_i$ thì $t \notin R_j$ với $j \neq i$ (ngoại trừ replication).

*Chứng minh*: Hàm `deterministic_hash` là deterministic và `successor(k)` trong Chord ring là duy nhất với mọi $k$ (với giả định không có hash collision và ring nhất quán). Do đó, mỗi tài liệu có đúng một primary node.

*Lưu ý quan trọng về replica*: Hệ thống lưu replica tại successor của primary node. Các bản sao này vi phạm Disjointness theo nghĩa strict — nhưng đây là **replication có chủ đích** (intentional redundancy), được Özsu & Valduriez cho phép ngoại lệ. Điều kiện Disjointness áp dụng cho dữ liệu gốc (primary copy), không cho bản sao.

---

### 3.4 Distributed Inverted Index: Thiết kế hai lớp lưu trữ

Chord DHT chỉ hỗ trợ exact-match lookup theo key. Để hỗ trợ keyword search (Bài toán 2), cần xây dựng lớp chỉ mục trên DHT.

**Quyết định thiết kế**: Tách lưu trữ thành hai lớp logic trên cùng một DHT ring:

| Lớp | Key | Value | Vai trò |
|:---|:---|:---|:---|
| **Index Layer** | `hash(keyword)` | `Set[DocID]` | Inverted index phân tán |
| **Content Layer** | `hash(DocID)` | JSON document | Lưu trữ tài liệu gốc |

**Biện minh cho thiết kế hai lớp**:

*Phương án thay thế — Gộp chung*: Lưu toàn bộ tài liệu trực tiếp tại key của keyword. Nhược điểm: một keyword phổ biến (ví dụ "love" xuất hiện trong 30/100 tài liệu) sẽ làm cho một node lưu trữ và truyền tải toàn bộ nội dung 30 tài liệu cho mỗi query — tạo hot-spot cả về lưu trữ lẫn băng thông.

*Lý do chọn hai lớp*:
1. **Giảm Communication Cost**: Index layer chỉ truyền `Set[DocID]` (vài chục bytes) qua mạng. Content lookup chỉ xảy ra cho tài liệu người dùng thực sự yêu cầu (lazy fetching). Trong hệ phân tán, communication cost là thành phần chi phí chiếm tỷ trọng lớn nhất: $\text{Total Cost} = \text{I/O Cost} + \text{CPU Cost} + \text{Communication Cost}$.
2. **Cho phép tính toán AND query cục bộ**: Posting lists được thu thập về node khởi tạo dưới dạng tập ID nhỏ gọn. Phép giao tập được tính toán in-memory tại initiator mà không cần truyền tải dữ liệu lớn qua mạng.
3. **Separation of Concerns**: Index layer và content layer có lifecycle khác nhau — index được cập nhật mỗi khi peer publish tài liệu mới; content ít thay đổi hơn. Tách rời giúp quản lý từng lớp độc lập.

**Trade-off phải thừa nhận**:
- **Tăng chi phí ghi**: Mỗi lần publish tài liệu cần ghi vào cả hai lớp — $1$ thông điệp `PUT_CONTENT` và $|\text{keywords}|$ thông điệp `PUT` cho inverted index.
- **Rủi ro "orphan index"**: Nếu content node sập sau khi index node đã cập nhật, index trỏ đến DocID mà content lookup sẽ trả về 404. Hệ thống chấp nhận đây là trạng thái nhất quán tạm thời, cần chu kỳ `maintain_data` để dọn dẹp.

---

## 4. XỬ LÝ TRUY VẤN PHÂN TÁN (Distributed Query Processing)

### 4.1 Mô hình Boolean Retrieval và AND Query

Đề tài chọn mô hình **Boolean Retrieval**: một tài liệu được coi là kết quả nếu nó chứa *tất cả* các từ khóa trong query (AND semantics). Mô hình này phù hợp với yêu cầu G3 của BRD và đơn giản hơn mô hình ranking (TF-IDF) vốn nằm ngoài phạm vi đề tài.

**Hạn chế cần thừa nhận**: Boolean AND query có thể trả về kết quả rỗng với các query quá cụ thể — đặc biệt với dataset nhỏ (100 tài liệu). Đây là trade-off chấp nhận được so với chi phí cài đặt ranking.

### 4.2 Quy trình xử lý query phân tán 4 bước

```
Chuỗi query từ người dùng (Web Dashboard)
                    ↓
[BƯỚC 1: TOKENIZATION] — In-memory tại Initiator Node
  - Lowercase, loại bỏ ký tự đặc biệt
  - Lọc stopwords (127 từ dừng tiếng Anh)
  - Loại bỏ token ngắn hơn 3 ký tự
  - Đầu ra: danh sách keyword tokens
                    ↓
[BƯỚC 2: DISTRIBUTED ROUTING] — DHT Finger Table Lookup
  - Mỗi keyword được băm: key_id = hash(keyword, m)
  - Chord routing tìm successor(key_id) qua finger table
  - Đầu ra: địa chỉ node chịu trách nhiệm + routing trace
                    ↓
[BƯỚC 3: POSTING LIST RETRIEVAL] — HTTP Message Passing
  - GET request đến node đích
  - Nhận Set[DocID] (index layer)
  - Ghi lại trace: peer path, hop count
                    ↓
[BƯỚC 4: INCREMENTAL INTERSECTION + EARLY STOP]
  - Tính giao tập tích lũy in-memory tại Initiator
  - Early stop khi giao tập rỗng
  - Content fetch (lazy) chỉ cho tài liệu được chọn
                    ↓
Kết quả + routing trace hiển thị trên Dashboard
```

**Lưu ý quan trọng**: Bước 2 và 3 được thực hiện **tuần tự** cho từng keyword (sequential fetch), không song song. Đây là một trade-off:
- *Song song* sẽ giảm latency tổng thể nhưng không cho phép Early Stop (vì tất cả request đã gửi đi trước khi nhận kết quả).
- *Tuần tự* cho phép Early Stop nhưng tăng latency khi không có early stop.

Với dataset 100 tài liệu và 8-10 node, số keyword sau tokenization thường là 2-4 token, nên latency của sequential fetch là chấp nhận được.

### 4.3 Chi phí Query và phân tích O(log N)

**Chi phí một keyword lookup**:
- Routing: $O(\log N)$ hops, mỗi hop là một HTTP roundtrip.
- Payload mỗi hop: thông điệp định tuyến (vài bytes header + node ID).
- Payload khi tìm thấy: `Set[DocID]` — tỷ lệ với số tài liệu chứa keyword đó.

**Chi phí AND query với $k$ keywords**:
- Trường hợp xấu nhất (không có early stop): $k \times O(\log N)$ hops.
- Trường hợp tốt (early stop sau keyword thứ $j$): $j \times O(\log N)$ hops, $j < k$.
- Lưu ý: $O(\log N)$ bound chỉ valid khi finger table nhất quán. Sau churn, số hop thực tế có thể lớn hơn do fallback về successor chaining.

**Chi phí thông điệp tổng thể (Message Complexity)**:
- Stabilization background: $O(\log N)$ thông điệp mỗi chu kỳ mỗi node.
- Replication: mỗi PUT sinh thêm 1-2 thông điệp STORE_REPLICA.
- Trong điều kiện churn cao, overhead stabilization có thể chiếm phần lớn tổng thông điệp.

---

## 5. PHÂN TÍCH CHỊU LỖI (Fault Tolerance Analysis)

### 5.1 Lựa chọn CAP: AP thay vì CP

Hệ thống P2P hoạt động trong môi trường có churn (node join/leave liên tục), tương đương với các sự kiện partition không thể tránh. Theo định lý CAP (Brewer 2000), khi partition xảy ra, hệ thống phải chọn giữa Consistency và Availability.

**Phân tích lựa chọn**:

- *CP (Consistency + Partition Tolerance)*: Hệ thống từ chối phục vụ request khi không thể đảm bảo consistency. Ví dụ: 2-Phase Commit chờ tất cả node xác nhận trước khi commit. Trong P2P với churn cao, node thường xuyên không phản hồi → hệ thống thường xuyên bị block. Không phù hợp.

- *AP (Availability + Partition Tolerance)*: Hệ thống tiếp tục phục vụ request dù có partition, chấp nhận một số node có thể trả về dữ liệu cũ. Phù hợp với P2P vì peer luôn có thể phục vụ query từ local store, kể cả khi không liên lạc được với tất cả peer khác.

**Lựa chọn AP** là hợp lý cho bài toán này vì:
- Dữ liệu thư viện có tần số ghi thấp so với tần số đọc — inconsistency tạm thời ít ảnh hưởng đến trải nghiệm người dùng.
- Availability là ưu tiên cao hơn trong P2P — hệ thống không nên "chết" chỉ vì một peer rời mạng.

### 5.2 Cơ chế Lazy Replication

**Thiết kế replication**: Mỗi key được replicate sang successor (replication factor = 2). Replication được thực hiện **asynchronously** (Lazy Replication) — không chờ replica xác nhận trước khi trả lời client.

**So sánh với Eager Replication**:

| | Lazy Replication | Eager Replication |
|:---|:---|:---|
| **Khi ghi** | Ghi primary xong → trả lời client → ghi replica sau | Ghi tất cả replica đồng thời → chờ xác nhận |
| **Availability** | Cao — không bị block khi replica node chậm/chết | Thấp — bị block khi bất kỳ replica node nào không phản hồi |
| **Consistency** | Eventual consistency | Stronger consistency |
| **Phù hợp với P2P?** | Có — churn không block write | Không — churn thường xuyên gây block |

**Chi phí Lazy Replication cần thừa nhận**:
- Có thể có khoảng thời gian ngắn mà primary đã cập nhật nhưng replica chưa — một client đọc từ replica node có thể nhận dữ liệu cũ.
- Khi primary node sập trước khi replica được sync, dữ liệu mới nhất có thể mất (durability risk).

### 5.3 Stabilization và Churn Handling

**Ba tiến trình nền của Chord**:

1. `stabilize()`: Mỗi node hỏi successor của mình xem có node nào mới join vào giữa không. Cập nhật successor nếu cần. Chi phí: 1 thông điệp mỗi chu kỳ.

2. `check_predecessor()`: Kiểm tra predecessor còn sống không. Nếu chết, set predecessor = None. Chi phí: 1 thông điệp mỗi chu kỳ.

3. `fix_fingers()`: Cập nhật một entry ngẫu nhiên trong finger table. Sau $O(\log N)$ chu kỳ, toàn bộ finger table được làm mới. Chi phí: 1 thông điệp mỗi chu kỳ.

**Replica Promotion**: Khi `check_predecessor` phát hiện predecessor chết, successor của node đó cần promote replica thành primary. Đây là tiến trình quan trọng để đảm bảo data không bị mất sau churn.

**Giới hạn của Stabilization**:
- Convergence time: ring cần nhiều chu kỳ stabilization để đạt trạng thái nhất quán sau churn. Trong thời gian này, một số lookup có thể thất bại hoặc định tuyến sai.
- Không xử lý được concurrent joins: nếu nhiều node join đồng thời, stabilization có thể hội tụ chậm hoặc tạm thời tạo vòng lặp.
- Không có cơ chế phát hiện churn nhanh — `check_predecessor` chỉ chạy theo chu kỳ định kỳ, không phải event-driven.

---

## 6. PHÂN TÍCH HIỆU NĂNG (Performance Analysis)

### 6.1 Routing Complexity

| Metric | Giá trị lý thuyết | Điều kiện |
|:---|:---|:---|
| Lookup hops | $O(\log N)$ expected | Finger table nhất quán |
| Finger table size | $m = 8$ entries (với $m=8$ bits) | Cố định theo thiết kế |
| Stabilization overhead | $O(1)$ thông điệp/chu kỳ/node | Background, không ảnh hưởng query |
| AND query cost (k keywords) | $k \times O(\log N)$ hops worst-case | Không có early stop |

### 6.2 Early Stop Heuristic

Khi thực hiện AND query tuần tự, nếu sau keyword thứ $j$, giao tập đã rỗng thì dừng lại. Heuristic này giảm số thông điệp mạng từ $k \times O(\log N)$ xuống $j \times O(\log N)$ với $j \leq k$.

Hiệu quả của early stop phụ thuộc vào thứ tự xử lý keyword. Một cải tiến tiềm năng (nằm ngoài phạm vi đề tài) là **selectivity-based ordering**: xử lý keyword có posting list ngắn nhất trước để early stop xảy ra sớm hơn.

### 6.3 Communication Cost Analysis

Trong hệ phân tán, $\text{Total Cost} = \text{I/O Cost} + \text{CPU Cost} + \text{Communication Cost}$. Communication cost thường chiếm tỷ trọng lớn nhất.

**Thiết kế hai lớp giảm Communication Cost**:
- Thay vì truyền toàn bộ JSON document qua mạng khi lookup keyword, chỉ truyền `Set[DocID]` (khoảng $|DocIDs| \times 4$ bytes).
- Content fetch chỉ xảy ra cho tài liệu người dùng thực sự yêu cầu — không phải toàn bộ kết quả.

**Overhead HTTP so với binary protocol**:
- Hệ thống dùng HTTP REST + JSON payload. HTTP header overhead (~200-500 bytes mỗi request) là không đáng kể so với JSON payload của tài liệu đầy đủ, nhưng có thể đáng kể so với thông điệp routing nhỏ.
- Trong môi trường production, một binary protocol (như gRPC) sẽ giảm overhead này. Đây là giới hạn chấp nhận được trong phạm vi học thuật.

---

## 7. TÓM TẮT TRADE-OFF (Trade-off Summary)

| Quyết định thiết kế | Lợi ích | Chi phí | Justification |
|:---|:---|:---|:---|
| **Structured P2P (Chord DHT)** thay vì Unstructured | Deterministic lookup, trace routing rõ ràng | Phải duy trì finger table, overhead stabilization | Yêu cầu G2, G4 của BRD đòi hỏi DHT routing và trace |
| **Chord** thay vì Kademlia | Ring đơn giản, dễ chứng minh, dễ unit test | Không có parallel routing | Phù hợp quy mô nhỏ, ưu tiên correctness |
| **AP** thay vì **CP** | Availability cao, không bị block khi churn | Eventual consistency — có thể đọc dữ liệu cũ | Churn không thể tránh trong P2P; dữ liệu thư viện ít thay đổi |
| **Lazy Replication** thay vì Eager | Không block write khi replica node chết | Durability risk trong window ngắn sau write | 2PC sẽ block khi churn cao |
| **Hai lớp lưu trữ** (Index + Content) | Giảm communication cost | Tăng write overhead, rủi ro orphan index | Communication cost là bottleneck chính trong WAN |
| **Sequential fetch + Early Stop** thay vì Parallel | Cho phép early stop, tiết kiệm thông điệp | Tăng latency khi không có early stop | Dataset nhỏ, số keyword ít — latency overhead chấp nhận được |
| **Homogeneous P2P** | Không cần schema mapping layer | Giảm tính tự trị — mọi peer phải dùng schema chung | Tất cả peer cài cùng phần mềm — schema đồng nhất là ràng buộc hợp lý |

---

## 8. CÁC THÀNH PHẦN LÝ THUYẾT ĐƯỢC LOẠI BỎ CÓ CHỦ ĐÍCH (Reasoned Exclusions)

### 8.1 Range Queries (BATON / Skip Graphs — Chương 9)

**Vấn đề với Chord và Range Query**: Consistent Hashing phân bổ key ngẫu nhiên lên vòng ring, phá vỡ trật tự tuyến tính của dữ liệu. Do đó, range query trên thuộc tính số (ví dụ: sách xuất bản từ 2010-2020) yêu cầu quét toàn bộ ring — chi phí $O(N)$ thay vì $O(\log N)$.

**Lý do loại bỏ**: Yêu cầu đề tài chỉ bao gồm exact-match keyword search (AND query). Range query theo thuộc tính số không nằm trong phạm vi (Out of Scope theo BRD Mục 3.2). Cài đặt BATON hay Skip Graphs sẽ tăng đáng kể độ phức tạp mà không mang lại lợi ích thực tế cho bài toán này.

### 8.2 Strong Consistency Protocols (OceanStore / Byzantine Agreement)

**Tại sao OceanStore không phù hợp**: OceanStore thiết kế cho dữ liệu quan trọng cần strong consistency (Byzantine fault tolerance). Chi phí: mỗi write yêu cầu $O(f)$ rounds of agreement với $f$ là số faulty node cho phép.

**Lý do loại bỏ**: Dữ liệu thư viện có tần số ghi thấp và không yêu cầu Byzantine fault tolerance (các peer là trusted trong môi trường học thuật). Chi phí của Byzantine Agreement vượt xa lợi ích consistency mang lại. Eventual consistency thông qua Lazy Replication là mức độ nhất quán phù hợp với bài toán.

### 8.3 Schema Mapping / Reformulation (Chương 9 — Heterogeneous P2P)

**Khi nào cần Schema Mapping**: Trong Heterogeneous P2P, mỗi peer có thể quản lý dữ liệu với schema khác nhau. Truy vấn từ peer này cần được "dịch" sang schema của peer khác (Pairwise Mapping hoặc Common Agreement Mapping).

**Lý do loại bỏ**: Hệ thống được thiết kế là **Homogeneous** — tất cả peer cài cùng phần mềm và chia sẻ cùng JSON schema cho tài liệu (định nghĩa tại `src/models.py`). Schema đồng nhất là ràng buộc thiết kế hợp lý vì tất cả peer đều do cùng một nhóm phát triển và cài đặt. Không có xung đột schema → Schema Mapping là không cần thiết.

*Lưu ý*: Nếu hệ thống mở rộng để tích hợp với các nguồn thư viện bên ngoài có schema khác nhau, đây sẽ là điểm cần xem xét lại.

---

> **Ghi chú về phạm vi báo cáo**: Báo cáo này tập trung vào phân tích lý thuyết và biện minh thiết kế. Mã nguồn (các hàm trong `node.py`, `storage_mixin.py`, `peer_server.py`) đóng vai trò bằng chứng hiện thực hóa các quyết định thiết kế, không phải trọng tâm phân tích. Mọi tuyên bố hiệu năng đều là ước lượng dựa trên phân tích lý thuyết, không phải benchmark thực nghiệm trên production system.

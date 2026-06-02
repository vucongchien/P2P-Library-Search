# rule:
bất kì cái nào không dùng thì k cần cố nhét vào, chỉ cần có lí do là được, các lí do thuyết phục như là , đề tài k cần , k phù hợp , k trong phạm vi , ...

# Chương 9:

## P2P
### Requirement for P2P data management:
- autonomy of peers: các nút có khả năng tham gia/ rời khỏi mạng bất cứ lúc nào và kiểm soát dữ liệu của mình với các nút tin cậy 

` [ tôi k chắc là cái câu  "có khả năng kiểm soát dữ liệu của mình với các nút tin cậy " là có trong đồ án của mình ... ] `


- Query expressiveness: Key-lookup, key-work search, SQL-like. 

`[ đồ án mình có cần có hết mấy thứ này k ? và hiện tại đang có cái nào ]` 

- Efficiency: Sử dụng hiểu quả băng thông, sức mạnh tính toán và lưu trữ.

` [tôi thấy là chúng ta chỉ có lưu trữ , chứ băng thông thì dùng rest là k tối ưu rồi 'tôi nói đúng k' , còn tính toán thì cũng k biết] `

- Quality of service (QoS): User-perceived efficiency: completeness of results, response time, data consistency.

- Fault-tolerance: Đảm bảo hiệu quả và QoS ngay cả khi có lỗi xảy ra.

` tôi k nghĩ là đề tài ta có thể chịu lỗi trong lúc đang tìm kiếm :v `

- Security: Kiểm soát truy cập dữ liệu trong bối cảnh hệ thống rất mở. ( của mình làm j có cái này )

### Peer Reference Architecture

sơ đồ bằng mermaid
```
flowchart LR
    %% User Interface
    UI["Data Management API / User Interface"]
    UI --> DM["Data Management Layer"]

    %% Data Management Layer components
    subgraph DM["Data Management Layer"]
        QM["Query Manager"]
        UM["Update Manager"]
        CM["Cache Manager"]
    end

    %% P2P Network Sublayer
    DM --> P2P["P2P Network Sublayer"]
    P2P --> Cloud["P2P Network"]

    %% Peers in the network
    Cloud --> Peer1["Peer"]
    Cloud --> Peer2["Peer"]
    Cloud --> Peer3["Peer"]

    %% Local Data Sources
    LDS["Local Data Source"]
    Wrapper["Wrapper"]
    SM["Semantic Mappings"]
    RDC["Remote Data Cache"]

    Wrapper --> LDS
    LDS --> DM
    SM --> DM
    RDC --> DM

```


` - kiến trúc của mình khác quá . hu hu , bạn thấy sao . ` 

### P2P Network Topologies
- có 2 loại pure là unstrucutre và structured , và có cả Super-peer hybrid , nhưng mà mình dùng : 
- là loại Pure P2P systems:
    - Structured systems (DHT)
        - CHORD

### Search over Distributed Index
- A peer sends the request for resource to all its neighbors
- Each neighbor propagates to its neighbors if it doesn’t have the resource
- The peer who has the resource responds by sending the resource

` đề tài ta dùng search như thế nào `

### Yêu cầu của structured P2P network ( xem đạt được j )

- Simple API with put(key, data) and get(key)
- The key (an object id) is hashed to generate a peer id, which stores  the corresponding data
- Efficient exact-match search
- O(log n) for put(key, data), get(key)
- Limited autonomy since a peer is responsible for a range of keys


### P2P Systems Comparison

| **Yêu cầu** | **Không cấu trúc (Unstructured)** | **Có cấu trúc (Structured)** | **Siêu-nút (Superpeer)** |
| --- | --- | --- | --- |
| **Tính tự trị (Autonomy)** | Thấp | Thấp | Trung bình |
| **Khả năng biểu đạt truy vấn (Query expressiveness)** | Cao | Thấp | Cao |
| **Hiệu quả (Efficiency)** | Thấp | Cao | Cao |
| **Chất lượng dịch vụ (QoS)** | Thấp | Cao | Cao |
| **Khả năng chịu lỗi (Fault-tolerance)** | Cao | Cao | Thấp |
| **Bảo mật (Security)** | Thấp | Thấp | Cao |

###  P2P Schema Mapping
Problem: support decentralized schema mapping so that a query expressed on one peer’s schema can be reformulated to a query on another peer’s schema
Main approaches
Pairwise schema mapping
Mapping based on machine learning
Common agreement mapping

` mình dùng cái nào k thì lọc ra `

### Querying over P2P Systems
P2P networks provide basic query routing
Sufficient for simple, exact-match queries, e.g. with a DHT
Supporting more complex queries, particularly in DHTs, is difficult
Main types of complex queries
Top-k queries
Join queries
Range queries

` mình dùng cái nào k thì lọc ra `

### Data Storage Mechanism

Two complementary methods for storing tuples in the DHT
Tuple storage: each tuple of a relation is stored in the DHT using its tuple’s identifier (e.g. primary key)
Allows to retrieve tuples using their identifier
Attribute storage: the values of some attributes of a tuple are stored individually in the DHT
Acts as secondary indices
Good support for exact match queries


#### Tuple Storage Method

Let 
R (a1, a2, …, am) be a relation
t 〈v1, v2, …, vm〉 be a tuple of R 
v1 be the primary key of tuple t
h : a hash function that hashes its inputs into a DHT key 
To store tuple t in the DHT, a peer does as follows:
   ts_key = h(R, v1);
   put(ts_key,〈v1, v2, …, vm〉);

#### Attribute-value Storage


#### DHTop
#### FD 

### Join Query Processing in DHTs, Range Query Processing , BATON , Range Query Processing in BATON

### Replica Consistency


Replica consistency in DHTs
Basic support  - Tapestry
Replica reconciliation - OceanStore


#### Tapestry
#### OceanStore

# chương 8: Parallel
## Partitioning Functions
Hashing
(k,v) assigned to node h(k)
Exact match queries
Problem with skew distribution

Range
(k,v) to the node that holds k's interval
Exact match and range queries
Needs an index on key

## Replicated Data Partitioning
High-availability requires data replication
Simple solution is mirrored disks
Hurts load balancing when one node fails
More elaborate solutions achieve load balancing
Interleaved partitioning (Teradata)
Chained partitioning (Gamma)
## Interleaved Partitioning
## Chained Partitioning
## Placement Directory

## Join Processing
# chương 6 replicate
## Distributed Centralized Eager `Lazy` Replication 
## copy 
## master slave
## strategy
##  protocol 
## 2 Phase protocol

# chương 4 query:
## Cost of Alternatives
## Query Optimization Objectives
Minimize a cost function
I/O cost + CPU cost + communication cost
These might have different weights in different distributed environments
Wide area networks 
Communication cost may dominate or vary much
Bandwidth
Speed
Protocol overhead
Local area networks
Communication cost not that dominant,so total cost function should be considered
Can also maximize throughput
## Complexity of Relational Operations
Assume 
Relations of cardinality n
Sequential scan

## Types Of Optimizers
### Heuristics
### Exhaustive search
## Optimization Granularity
## Optimization Decision Sites
## Network Topology
## Reduction for PHF ... 

# chương 2: distrubute design 
## Fragmentation

Horizontal Fragmentation (HF)
Primary Horizontal Fragmentation (PHF)
Derived Horizontal Fragmentation (DHF)
Vertical Fragmentation (VF)
Hybrid Fragmentation (HF)



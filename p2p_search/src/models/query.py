from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from enum import Enum

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"

class ResultStatus(str, Enum):
    HAS_RESULT = "HAS_RESULT"
    EMPTY = "EMPTY"

@dataclass
class HopEvent:
    """Đại diện cho 1 bước nhảy mạng (Routing Hop)."""
    hop_number: int
    from_node: int
    to_node: int
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hop": self.hop_number,
            "from": self.from_node,
            "to": self.to_node,
            "reason": self.reason
        }

@dataclass
class KeywordLookup:
    """Thông tin Trace của một từ khóa trong khi tìm kiếm."""
    keyword: str
    hash_value: int
    responsible_peer: Optional[int]
    posting_list: List[int] # Set convert to List for JSON
    hops: int = 0
    routing_path: List[HopEvent] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "hash_value": self.hash_value,
            "responsible_peer": self.responsible_peer,
            "posting_list": self.posting_list,
            "hops": self.hops,
            "routing_path": [h.to_dict() for h in self.routing_path]
        }

@dataclass
class QueryResult:
    """Kết quả trả về chính thức của QueryEngine chưng cất."""
    query: str
    execution_status: ExecutionStatus
    result_status: ResultStatus
    total_hops: int
    initiator_peer: int
    final_result: List[int]
    
    flags: Dict[str, bool] = field(default_factory=lambda: {
        "early_stop": False,
        "partial_data": False
    })
    warnings: List[str] = field(default_factory=list)
    trace: List[KeywordLookup] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "execution_status": self.execution_status.value,
            "result_status": self.result_status.value,
            "total_hops": self.total_hops,
            "initiator_peer": self.initiator_peer,
            "final_result": self.final_result,
            "flags": self.flags,
            "warnings": self.warnings,
            "trace": [k.to_dict() for k in self.trace]
        }

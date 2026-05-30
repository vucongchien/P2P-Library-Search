"""
Routing Trace Models — Source of Truth cho đường đi routing.

Mỗi node trong quá trình routing tự ghi lại quyết định của mình.
Path tích lũy qua từng hop → trace chính xác 100%.
Serializable (dict/JSON) → hoạt động cả Local lẫn Network.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class RoutingHop:
    """
    Một bước nhảy THỰC TẾ trong quá trình routing.
    Được tạo bởi chính node thực hiện quyết định.
    """
    node_id: int                # Node thực hiện quyết định
    action: str                 # "ORIGIN" | "FORWARD" | "RESOLVED" | "SELF"
    target_key: int             # key đang tìm
    next_node: Optional[int]    # node tiếp theo (nếu FORWARD) hoặc successor (nếu RESOLVED)
    reason: str                 # lý do chính xác (e.g., "key 73 ∈ (60, 110]")
    latency_ms: Optional[float] = None  # Thời gian hoàn thành nếu có gửi mạng

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": self.node_id,
            "action": self.action,
            "target_key": self.target_key,
            "next_node": self.next_node,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingHop":
        return cls(
            node_id=data["node"],
            action=data["action"],
            target_key=data["target_key"],
            next_node=data.get("next_node"),
            reason=data["reason"],
            latency_ms=data.get("latency_ms"),
        )


@dataclass
class RoutingTrace:
    """
    Kết quả routing đầy đủ — source of truth.
    Chứa đường đi chính xác từ node khởi tạo đến node đích.
    """
    key: int                          # key đang tìm
    target_id: int                    # node chịu trách nhiệm key
    path: List[RoutingHop] = field(default_factory=list)
    success: bool = True

    @property
    def hop_count(self) -> int:
        """Số hop thực tế (không tính ORIGIN)."""
        return len([h for h in self.path if h.action != "ORIGIN"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "target_id": self.target_id,
            "path": [h.to_dict() for h in self.path],
            "success": self.success,
            "hop_count": self.hop_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingTrace":
        return cls(
            key=data["key"],
            target_id=data["target_id"],
            path=[RoutingHop.from_dict(h) for h in data.get("path", [])],
            success=data.get("success", True),
        )

    def format_readable(self) -> str:
        """In routing path dạng đọc được cho debug/test."""
        lines = [f"  Route for key={self.key} -> target=N{self.target_id} ({self.hop_count} hops)"]
        for i, hop in enumerate(self.path):
            prefix = "  |-" if i < len(self.path) - 1 else "  \\-"
            arrow = ""
            if hop.next_node is not None:
                arrow = f" --> N{hop.next_node}"
            lat_str = f" [{hop.latency_ms:.1f}ms]" if getattr(hop, "latency_ms", None) is not None else ""
            lines.append(f"{prefix} [{hop.action}] N{hop.node_id}{arrow}{lat_str}  ({hop.reason})")
        return "\n".join(lines)

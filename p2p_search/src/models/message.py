from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Message:
    """Represents a message sent between nodes in the Chord DHT."""
    type: str           # The type of message (e.g., FIND_SUCCESSOR, PUT, GET)
    sender_id: int      # The ID of the node sending the message
    payload: Dict[str, Any] = field(default_factory=dict) # The actual content payload
    ttl: int = 20       # Time-To-Live to prevent infinite routing loops
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary for network transport."""
        return {
            "type": self.type,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "ttl": self.ttl
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize message from dictionary."""
        return cls(
            type=data["type"],
            sender_id=data["sender_id"],
            payload=data.get("payload", {}),
            ttl=data.get("ttl", 20)
        )

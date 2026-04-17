from dataclasses import dataclass
from typing import Dict, Any

class ErrorCode:
    """Standardized error codes for Chord DHT communication and routing."""
    
    # === Transport Layer ===
    NODE_NOT_FOUND    = "NODE_NOT_FOUND"      # node_id not found in registry
    NODE_UNREACHABLE  = "NODE_UNREACHABLE"    # network connection refused/timeout
    TIMEOUT           = "TIMEOUT"             # message timeout
    
    # === Chord Layer ===
    ROUTING_FAILED    = "ROUTING_FAILED"      # Cannot find successor despite retries
    ROUTING_LOOP      = "ROUTING_LOOP"        # Infinite loop detected (ttl=0)
    STALE_FINGER      = "STALE_FINGER"        # Finger pointed to dead node
    KEY_NOT_FOUND     = "KEY_NOT_FOUND"       # Key not present in DHT
    UNKNOWN_TYPE      = "UNKNOWN_TYPE"        # Message type not supported
    
    # === Application Layer ===
    INVALID_QUERY     = "INVALID_QUERY"       # Query format incorrect
    PARTIAL_FAILURE   = "PARTIAL_FAILURE"     # Some keywords failed lookup
    EMPTY_RESULT      = "EMPTY_RESULT"        # Empty intersection from successful lookup
    INDEX_BUILD_FAIL  = "INDEX_BUILD_FAIL"    # Publishing keyword failed

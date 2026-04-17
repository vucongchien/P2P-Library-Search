import pytest
from src.models import ErrorCode, Message, Response

class TestModels:
    def test_message_initialization_and_default_ttl(self):
        """Test that Message uses a default ttl of 20 and can be created."""
        msg = Message(type="FIND_SUCCESSOR", sender_id=10, payload={"key": 42})
        assert msg.type == "FIND_SUCCESSOR"
        assert msg.sender_id == 10
        assert msg.payload == {"key": 42}
        assert msg.ttl == 20  # Default value should be active

    def test_message_serialization(self):
        """Test Message serialization to and from dict."""
        original_msg = Message(type="PUT", sender_id=5, payload={"doc": "data"}, ttl=15)
        
        # Serialize
        serialized = original_msg.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["type"] == "PUT"
        assert serialized["ttl"] == 15
        
        # Deserialize
        reconstructed_msg = Message.from_dict(serialized)
        assert reconstructed_msg.type == original_msg.type
        assert reconstructed_msg.sender_id == original_msg.sender_id
        assert reconstructed_msg.payload == original_msg.payload
        assert reconstructed_msg.ttl == original_msg.ttl

    def test_response_serialization(self):
        """Test Response serialization to and from dict."""
        original_res = Response(success=False, data={}, error=ErrorCode.NODE_NOT_FOUND)
        
        # Serialize
        serialized = original_res.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["success"] is False
        assert serialized["error"] == "NODE_NOT_FOUND"
        
        # Deserialize
        reconstructed_res = Response.from_dict(serialized)
        assert reconstructed_res.success == original_res.success
        assert reconstructed_res.data == original_res.data
        assert reconstructed_res.error == original_res.error

    def test_response_optional_params(self):
        """Test Response with default values."""
        res = Response(success=True)
        assert res.success is True
        assert res.data == {}
        assert res.error is None
        
    def test_error_codes_availability(self):
        """Test that ErrorCode exposes right symbols."""
        assert ErrorCode.ROUTING_LOOP == "ROUTING_LOOP"
        assert ErrorCode.TIMEOUT == "TIMEOUT"

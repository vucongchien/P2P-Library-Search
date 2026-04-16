from src.models import ProcessedDocument
from src.index_builder import build_inverted_index, build_peer_indexes

def test_build_inverted_index():
    docs = [
        ProcessedDocument(1, "A", "C", ["peer", "network"], "raw1"),
        ProcessedDocument(2, "B", "C", ["peer", "node"], "raw2")
    ]
    
    idx = build_inverted_index(docs)
    
    assert "peer" in idx
    assert idx["peer"] == {1, 2}
    
    assert "network" in idx
    assert idx["network"] == {1}
    
    assert "node" in idx
    assert idx["node"] == {2}

def test_build_peer_indexes():
    # 4 docs, 2 peers -> chunk size = 2
    docs = [
        ProcessedDocument(1, "A", "C", ["a"], "raw1"),
        ProcessedDocument(2, "B", "C", ["b"], "raw2"),
        ProcessedDocument(3, "C", "C", ["c"], "raw3"),
        ProcessedDocument(4, "D", "C", ["d"], "raw4")
    ]
    
    peer_idx = build_peer_indexes(docs, num_peers=2)
    
    assert "peer_0" in peer_idx
    assert "peer_1" in peer_idx
    
    # Doc 1, 2 go to peer 0
    assert "a" in peer_idx["peer_0"]
    assert "b" in peer_idx["peer_0"]
    assert "c" not in peer_idx["peer_0"]
    
    # Doc 3, 4 go to peer 1
    assert "c" in peer_idx["peer_1"]
    assert "d" in peer_idx["peer_1"]
    assert "a" not in peer_idx["peer_1"]

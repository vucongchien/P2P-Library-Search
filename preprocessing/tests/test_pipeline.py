import pytest
import os
import tempfile
import json
from preprocessing.models import ProcessedDoc
from preprocessing.pipeline import (
    load_dataset,
    validate_docs,
    clean_text,
    tokenize,
    preprocess_all,
    build_global_index,
    partition_index,
    save_json
)

@pytest.fixture
def mock_filepath():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(curr_dir, 'mock_data.json')

def test_phase1_validate(mock_filepath):
    raw_docs = load_dataset(mock_filepath)
    valid_docs, skip_reasons, warnings = validate_docs(raw_docs)
    
    # Có 6 docs:
    # id 1: valid
    # id 2: valid
    # id 3: valid (null title handled)
    # id 4: invalid (empty content)
    # id 5: invalid (missing content)
    # dup id 2: valid structure nhưng warning và skip vi dup id
    assert len(valid_docs) == 3
    
    ids = [v["id"] for v in valid_docs]
    assert 1 in ids
    assert 2 in ids
    assert 3 in ids
    
    # Warning cho duplicate ID
    assert any("duplicated id" in w for w in warnings)
    # Warning cho null title
    assert any("null title" in w for w in warnings)
    
    # Skip expected cho doc id 4 và 5
    assert len(skip_reasons) == 2 

def test_phase2_clean():
    title = "The P2P Voyager!"
    content = "A decentralized universe using PEER node. 1234!!!"
    cleaned = clean_text(title, content)
    # 1234 bị xoá, ! bị xoá
    assert cleaned == "the p p voyager a decentralized universe using peer node"

def test_phase3_tokenize():
    text = "the p p voyager a decentralized universe using peer node"
    tokens = tokenize(text)
    # "the", "a" là stopword -> bỏ
    # "p" < 3 char -> bỏ
    # Còn: "voyager", "decentralized", "universe", "using", "peer", "node" -> 6 elements
    assert "voyager" in tokens
    assert "decentralized" in tokens
    assert "the" not in tokens
    assert "p" not in tokens
    assert len(tokens) == 6

def test_phase4_index():
    docs = [
        ProcessedDoc(id=1, title="A", category="A", tokens=["system", "node"], raw_content=""),
        ProcessedDoc(id=2, title="B", category="B", tokens=["system", "database"], raw_content=""),
    ]
    
    global_index = build_global_index(docs)
    assert "system" in global_index
    assert global_index["system"] == {1, 2}
    assert "node" in global_index
    assert global_index["node"] == {1}
    assert "database" in global_index
    assert global_index["database"] == {2}

def test_phase4_partition():
    docs = [
        ProcessedDoc(id=1, title="A", category="A", tokens=["system"], raw_content=""),
        ProcessedDoc(id=2, title="B", category="B", tokens=["database"], raw_content=""),
        ProcessedDoc(id=3, title="C", category="C", tokens=["node"], raw_content=""),
        ProcessedDoc(id=4, title="D", category="D", tokens=["system", "node"], raw_content="")
    ]
    peer_indexes = partition_index(docs, num_peers=2)
    # 4 doc chia 2 -> peer_0 lấy 2 doc đầu, peer_1 lấy 2 doc cuối
    assert "peer_0" in peer_indexes
    assert "peer_1" in peer_indexes
    
    p0 = peer_indexes["peer_0"]
    assert p0["system"] == {1}
    assert p0["database"] == {2}
    assert "node" not in p0
    
    p1 = peer_indexes["peer_1"]
    assert p1["node"] == {3, 4}
    assert p1["system"] == {4}
    assert "database" not in p1

def test_phase5_serialize():
    with tempfile.TemporaryDirectory() as tmpdir:
        docs = [
            ProcessedDoc(id=1, title="A", category="A", tokens=["system", "node"], raw_content="raw a")
        ]
        out_path = os.path.join(tmpdir, "processed_docs.json")
        save_json(docs, out_path)
        
        assert os.path.exists(out_path)
        with open(out_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["id"] == 1
            assert data[0]["tokens"] == ["node", "system"] or data[0]["tokens"] == ["system", "node"]

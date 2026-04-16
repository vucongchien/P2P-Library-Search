import os
import pytest
from src.loader import load_dataset

MOCK_FILE = os.path.join(os.path.dirname(__file__), "mock_data", "sample_stories.json")

def test_load_dataset_valid_and_invalid_cases():
    docs, report = load_dataset(MOCK_FILE)
    
    assert report["total_raw"] == 6
    assert report["total_valid"] == 2
    assert report["total_skipped"] == 4
    
    assert len(docs) == 2
    assert docs[0].id == 1
    assert docs[0].title == "The P2P Voyager"
    
    assert docs[1].id == 2
    assert docs[1].title == "The Golden Index"

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_dataset("non_existent_file.json")

def test_invalid_json(tmpdir):
    p = tmpdir.join("bad.json")
    p.write("{ bad json ")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_dataset(str(p))

def test_not_a_list(tmpdir):
    p = tmpdir.join("obj.json")
    p.write('{"id": 1}')
    with pytest.raises(ValueError, match="JSON root must be a list"):
        load_dataset(str(p))

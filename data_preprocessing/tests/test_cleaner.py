from src.cleaner import clean_text

def test_clean_text():
    title = "The P2P Voyager"
    content = "In a decentralized universe, every star acts as a peer node. Node-123!"
    
    cleaned = clean_text(title, content)
    
    assert cleaned == "the p p voyager in a decentralized universe every star acts as a peer node node"

def test_clean_text_empty():
    assert clean_text("", "") == ""

def test_clean_text_only_special():
    assert clean_text("@#$$%", "1234") == ""

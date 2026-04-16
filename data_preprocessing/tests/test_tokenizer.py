from src.tokenizer import tokenize

def test_tokenize():
    text = "the voyager is an act of peer node peer node"
    tokens = tokenize(text)
    
    # 'the', 'is', 'an', 'of' -> stopwords or short
    # 'act', 'peer', 'node', 'peer', 'node', 'voyager' -> distinct
    assert sorted(tokens) == sorted(['act', 'peer', 'node', 'voyager'])

def test_tokenize_short_words():
    assert tokenize("ab c def g") == ["def"]

def test_tokenize_stopwords():
    assert tokenize("this is the and of it") == []

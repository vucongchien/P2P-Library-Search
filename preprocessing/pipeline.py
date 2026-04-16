import json
import re
import os
from typing import List, Dict, Set, Tuple, Any
from .models import ProcessedDoc, PreprocessingReport

# Hardcoded Mức độ cơ bản tiếng Anh Stopwords
STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
    'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
    'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
    'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should',
    "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't",
    'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't",
    'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't",
    'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
}

def load_dataset(filepath: str) -> List[Dict]:
    """Phase 1.1: Load JSON dataset."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset file not found: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def validate_docs(raw_docs: List[Dict]) -> Tuple[List[Dict], List[str], List[str]]:
    """Phase 1.2 & 1.3: Validate docs.
    Returns: (valid_docs, skip_reasons, warnings)
    """
    valid_docs = []
    skip_reasons = []
    warnings = []
    seen_ids = set()

    for idx, doc in enumerate(raw_docs):
        # Kiểm tra field tồn tại
        if not isinstance(doc, dict):
            skip_reasons.append(f"Doc at index {idx} format invalid (not dict).")
            continue
            
        doc_id = doc.get("id")
        title = doc.get("title", "")
        category = doc.get("category", "")
        content = doc.get("content")

        # Fallback empty string nếu None
        if title is None:
            title = ""
            warnings.append(f"Doc index {idx} (ID: {doc_id}) has null title, using empty string.")
            
        if category is None:
            category = ""

        # Validation: content
        if not content or not str(content).strip():
            skip_reasons.append(f"Doc index {idx} (ID: {doc_id}) skipped: Content is empty/null.")
            continue
            
        # Validation: id
        if doc_id is None:
            skip_reasons.append(f"Doc index {idx} skipped: Missing 'id'.")
            continue
            
        if doc_id in seen_ids:
            warnings.append(f"Doc {doc_id} duplicated id, keeping the first occurrence.")
            continue

        seen_ids.add(doc_id)
        valid_docs.append({
            "id": doc_id,
            "title": str(title),
            "category": str(category),
            "content": str(content)
        })

    return valid_docs, skip_reasons, warnings

def clean_text(title: str, content: str) -> str:
    """Phase 2: Text Extraction & Cleaning.
    Goal: Lowercase, remove special characters, and normalize whitespace.
    """
    text = f"{title} {content}"
    
    # Lowercase
    text = text.lower()
    
    # Xóa ký tự đặc biệt, chỉ giữ lại a-z và space
    text = re.sub(r'[^a-z\s]', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def tokenize(text: str) -> List[str]:
    """Phase 3: Tokenize & Normalize.
    Goal: Split by whitespace, remove stopwords and short tokens (<3 chars), deduplicate per doc.
    """
    # Split by whitespace
    raw_tokens = text.split()
    
    # Bỏ Stopwords và từ < 3 ký tự
    tokens = [t for t in raw_tokens if t not in STOPWORDS and len(t) >= 3]
    
    # Deduplication per doc
    unique_tokens = list(set(tokens))
    
    # Sort just for deterministic results in testing
    unique_tokens.sort()
    
    return unique_tokens

def preprocess_all(raw_docs: List[Dict]) -> Tuple[List[ProcessedDoc], PreprocessingReport]:
    """Process all data and generate report."""
    total_raw = len(raw_docs)
    valid_docs, skip_reasons, warnings = validate_docs(raw_docs)
    
    processed_docs = []
    global_vocab = set()
    
    for doc in valid_docs:
        cleaned_text = clean_text(doc["title"], doc["content"])
        tokens = tokenize(cleaned_text)
        global_vocab.update(tokens)
        
        processed = ProcessedDoc(
            id=doc["id"],
            title=doc["title"],
            category=doc["category"],
            tokens=tokens,
            raw_content=doc["content"]
        )
        processed_docs.append(processed)
        
    report = PreprocessingReport(
        total_raw=total_raw,
        total_valid=len(processed_docs),
        total_skipped=len(skip_reasons),
        skip_reasons=skip_reasons,
        vocabulary_size=len(global_vocab),
        warnings=warnings
    )
    
    return processed_docs, report

def build_global_index(processed_docs: List[ProcessedDoc]) -> Dict[str, Set[int]]:
    """Phase 4.1: Build Inverted Index."""
    inverted_index: Dict[str, Set[int]] = {}
    for doc in processed_docs:
        for token in doc.tokens:
            if token not in inverted_index:
                inverted_index[token] = set()
            inverted_index[token].add(doc.id)
    return inverted_index

def partition_index(processed_docs: List[ProcessedDoc], num_peers: int = 5) -> Dict[str, Dict[str, Set[int]]]:
    """Phase 4.3: Partition index theo peer."""
    # Sắp xếp doc theo id để chia cho có trật tự
    sorted_docs = sorted(processed_docs, key=lambda d: d.id)
    peer_indexes: Dict[str, Dict[str, Set[int]]] = {}
    
    import math
    chunk_size = math.ceil(len(sorted_docs) / num_peers) if num_peers > 0 and len(sorted_docs) > 0 else 0
    
    for i in range(num_peers):
        peer_id = f"peer_{i}"
        peer_indexes[peer_id] = {}
        
        if chunk_size == 0:
            continue
            
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        docs_for_peer = sorted_docs[start_idx:end_idx]
        
        for doc in docs_for_peer:
            for token in doc.tokens:
                if token not in peer_indexes[peer_id]:
                    peer_indexes[peer_id][token] = set()
                peer_indexes[peer_id][token].add(doc.id)
                
    return peer_indexes

def set_default(obj):
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError

def save_json(data: Any, filepath: str):
    """Phase 5: Serialize Output."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=set_default, indent=2, ensure_ascii=False)

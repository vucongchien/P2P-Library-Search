import math
from typing import Dict, Set, List
from .models import ProcessedDocument

def build_inverted_index(docs: List[ProcessedDocument]) -> Dict[str, Set[int]]:
    """
    Builds a global inverted index from a list of ProcessedDocuments.
    Format: keyword -> set(doc_ids)
    """
    index: Dict[str, Set[int]] = {}
    
    for doc in docs:
        for token in doc.tokens:
            if token not in index:
                index[token] = set()
            index[token].add(doc.id)
            
    return index

def build_peer_indexes(docs: List[ProcessedDocument], num_peers: int = 5) -> Dict[str, Dict[str, Set[int]]]:
    """
    Partitions documents as chunks among peers and builds local inverted index.
    """
    peer_indexes = {f"peer_{i}": {} for i in range(num_peers)}
    docs_sorted = sorted(docs, key=lambda d: d.id)
    
    chunk_size = math.ceil(len(docs_sorted) / num_peers) if num_peers > 0 else len(docs_sorted)
    
    for i, doc in enumerate(docs_sorted):
        peer_idx = i // chunk_size if chunk_size > 0 else 0
        if peer_idx >= num_peers:
            peer_idx = num_peers - 1  # safety catch
        
        peer_id = f"peer_{peer_idx}"
        local_idx = peer_indexes[peer_id]
        
        for token in doc.tokens:
            if token not in local_idx:
                local_idx[token] = set()
            local_idx[token].add(doc.id)
            
    return peer_indexes

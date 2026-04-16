import os
import json
import logging
from dataclasses import asdict

from src.loader import load_dataset
from src.cleaner import clean_text
from src.tokenizer import tokenize
from src.index_builder import build_inverted_index, build_peer_indexes
from src.models import ProcessedDocument

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def run_pipeline(input_path: str, output_dir: str, num_peers: int = 5):
    """
    Runs the full dataset preprocessing pipeline.
    """
    # 1. Load & Validate
    logging.info("Phase 1: Loading & Validating...")
    raw_docs, report = load_dataset(input_path)
    
    # 2. Text Extraction, Cleaning & Tokenize
    logging.info("Phase 2 & 3: Cleaning & Tokenizing...")
    processed_docs = []
    
    for raw in raw_docs:
        text = clean_text(raw.title, raw.content)
        tokens = tokenize(text)
        
        proc_doc = ProcessedDocument(
            id=raw.id,
            title=raw.title,
            category=raw.category,
            tokens=tokens,
            raw_content=raw.content
        )
        processed_docs.append(proc_doc)
        
    report["vocabulary_size"] = len(set(t for d in processed_docs for t in d.tokens))
    
    # 4. Build Indexes
    logging.info("Phase 4: Building Indexes...")
    global_index = build_inverted_index(processed_docs)
    peer_indexes = build_peer_indexes(processed_docs, num_peers=num_peers)
    
    # 5. Serialize Output
    logging.info("Phase 5: Serializing Output...")
    os.makedirs(output_dir, exist_ok=True)
    
    docs_path = os.path.join(output_dir, "processed_docs.json")
    global_index_path = os.path.join(output_dir, "inverted_index.json")
    peer_indexes_path = os.path.join(output_dir, "peer_local_indexes.json")
    report_path = os.path.join(output_dir, "preprocessing_report.json")
    
    with open(docs_path, "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in processed_docs], f, indent=2, ensure_ascii=False)
        
    with open(global_index_path, "w", encoding="utf-8") as f:
        serializable_global = {k: list(v) for k, v in global_index.items()}
        json.dump(serializable_global, f, indent=2)
        
    with open(peer_indexes_path, "w", encoding="utf-8") as f:
        serializable_peer = {
            peer: {k: list(v) for k, v in index.items()} 
            for peer, index in peer_indexes.items()
        }
        json.dump(serializable_peer, f, indent=2)
        
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    logging.info(f"Pipeline finished! Check {output_dir}")
    
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=r"E:\LEARN\HTPT\p2p_library_100_stories.json")
    parser.add_argument("--output", type=str, default=r"E:\LEARN\HTPT\data_preprocessing\output")
    parser.add_argument("--peers", type=int, default=5)
    
    args = parser.parse_args()
    
    run_pipeline(args.input, args.output, args.peers)

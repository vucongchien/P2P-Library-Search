import os
from preprocessing.pipeline import (
    load_dataset,
    preprocess_all,
    build_global_index,
    partition_index,
    save_json
)

def run():
    # Cấu hình path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "p2p_library_100_stories.json")
    output_dir = os.path.join(base_dir, "dataset", "processed")
    
    print(f"Loading dataset from: {input_file}")
    raw_docs = load_dataset(input_file)
    
    print("Preprocessing...")
    processed_docs, report = preprocess_all(raw_docs)
    
    print("Building Global Index...")
    global_index = build_global_index(processed_docs)
    
    print("Partitioning Index to Peers...")
    peer_indexes = partition_index(processed_docs, num_peers=5)
    
    print("Saving outputs...")
    save_json(processed_docs, os.path.join(output_dir, "processed_docs.json"))
    save_json(global_index, os.path.join(output_dir, "inverted_index.json"))
    save_json(peer_indexes, os.path.join(output_dir, "peer_local_indexes.json"))
    save_json(report, os.path.join(output_dir, "preprocessing_report.json"))
    
    print("Done! Check output in dataset/processed/")
    print(f"Report: Vcab={report.vocabulary_size}, Valid={report.total_valid}, Skipped={report.total_skipped}")

if __name__ == "__main__":
    run()

import argparse
from src.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="P2P Library Search - Dataset Preprocessing")
    parser.add_argument("--input", type=str, default=r"E:\LEARN\HTPT\p2p_library_100_stories.json", help="Path to input raw dataset")
    parser.add_argument("--output", type=str, default=r"E:\LEARN\HTPT\data_preprocessing\output", help="Directory to save output files")
    parser.add_argument("--peers", type=int, default=5, help="Number of peers for chunking")
    
    args = parser.parse_args()
    run_pipeline(args.input, args.output, args.peers)

if __name__ == "__main__":
    main()

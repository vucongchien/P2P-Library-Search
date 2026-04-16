import json
import logging
from typing import List, Dict, Any, Tuple
from .models import RawDocument

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def load_dataset(file_path: str) -> Tuple[List[RawDocument], Dict[str, Any]]:
    """
    Loads JSON dataset and validates required fields.
    Returns a tuple of (valid_docs, report_stats)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON format in {file_path}: {e}")
        raise ValueError(f"Invalid JSON: {e}")

    valid_docs = []
    seen_ids = set()
    
    report = {
        "total_raw": len(data) if isinstance(data, list) else 0,
        "total_valid": 0,
        "total_skipped": 0,
        "skip_reasons": []
    }
    
    if not isinstance(data, list):
         raise ValueError("JSON root must be a list")

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            reason = f"Item at idx {idx} is not a dictionary."
            report["skip_reasons"].append(reason)
            report["total_skipped"] += 1
            logging.warning(reason)
            continue
            
        doc_id = item.get("id")
        title = item.get("title", "")
        category = item.get("category", "")
        content = item.get("content")

        if doc_id is None:
            reason = f"Missing 'id' at idx {idx}"
            logging.warning(reason)
            report["skip_reasons"].append(reason)
            report["total_skipped"] += 1
            continue

        if doc_id in seen_ids:
            reason = f"Duplicate 'id' {doc_id} at idx {idx}"
            logging.warning(reason)
            report["skip_reasons"].append(reason)
            report["total_skipped"] += 1
            continue

        if not content or not str(content).strip():
            reason = f"Missing or empty 'content' for id {doc_id}"
            logging.warning(reason)
            report["skip_reasons"].append(reason)
            report["total_skipped"] += 1
            continue

        seen_ids.add(doc_id)
        valid_docs.append(RawDocument(
            id=doc_id,
            title=str(title),
            category=str(category),
            content=str(content)
        ))

    report["total_valid"] = len(valid_docs)
    return valid_docs, report

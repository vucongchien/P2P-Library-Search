from dataclasses import dataclass
from typing import List, Dict, Set, Optional

@dataclass
class ProcessedDoc:
    id: int
    title: str
    category: str
    tokens: List[str]       # unique tokens sau clean
    raw_content: str        # giữ nguyên để fetch back sau này nếu cần

@dataclass
class PreprocessingReport:
    total_raw: int
    total_valid: int
    total_skipped: int
    skip_reasons: List[str]
    vocabulary_size: int
    warnings: List[str]

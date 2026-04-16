"""
Models for data representation.
"""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RawDocument:
    id: int
    title: str
    category: str
    content: str

@dataclass
class ProcessedDocument:
    id: int
    title: str
    category: str
    tokens: List[str]
    raw_content: str

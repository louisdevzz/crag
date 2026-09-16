"""Shared text utilities for the ingestion and BM25 retrieval pipelines."""
from __future__ import annotations

from typing import List


def tokenize_vi(text: str) -> List[str]:
    """Tokenize Vietnamese text for lexical BM25 matching."""
    cleaned = text.lower().replace(",", " ").replace(".", " ").replace(";", " ").replace(":", " ")
    return [w for w in cleaned.split() if len(w) > 1]

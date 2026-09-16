"""BM25 Lexical Retrieval Module using rank-bm25."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROCESSED_DATA_DIR, TOP_K_BM25
from ingestion.text import tokenize_vi
from logging_config import get_logger

log = get_logger(__name__)


_BM25_CACHE: Optional[Dict[str, Any]] = None


def load_bm25_index(index_path: Path | str = PROCESSED_DATA_DIR / "bm25_index.pkl") -> Dict[str, Any]:
    """Load serialized BM25 index and provision catalog.

    No document has been ingested yet (or the index has not been rebuilt since):
    degrade to an empty corpus instead of raising, so `crag_search` can still
    complete and hand off to `controlled_web_search` via a normal AMBIGUOUS/
    INCORRECT decision rather than crashing the whole tool call.
    """
    global _BM25_CACHE
    index_path = Path(index_path)

    if _BM25_CACHE is not None:
        return _BM25_CACHE

    if not index_path.exists():
        log.warning(
            "BM25 index not found at %s -> treating as empty corpus (ingest a document "
            "via the Admin panel to enable lexical search)", index_path,
        )
        return {"bm25": None, "chunks": [], "count": 0}

    with open(index_path, "rb") as f:
        _BM25_CACHE = pickle.load(f)

    return _BM25_CACHE


def bm25_retrieve(
    query: str,
    top_k: int = TOP_K_BM25,
    index_path: Path | str = PROCESSED_DATA_DIR / "bm25_index.pkl",
) -> List[Dict[str, Any]]:
    """Retrieve top-K candidates using exact lexical BM25Okapi scoring.

    Parameters
    ----------
    query : str
        User search query (handles exact document numbers, Article numbers, and terms).
    top_k : int
        Number of candidates to retrieve.

    Returns
    -------
    list of dict
        Candidate records with BM25 scores.
    """
    index_data = load_bm25_index(index_path)
    bm25 = index_data["bm25"]
    chunks = index_data.get("chunks", index_data.get("provisions", []))
    if bm25 is None or not chunks:
        return []

    tokenized_query = tokenize_vi(query)
    if not tokenized_query:
        return []

    raw_scores = bm25.get_scores(tokenized_query)
    # Get top-k indices
    ranked_indices = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)[:top_k]

    max_score = max(raw_scores) if len(raw_scores) > 0 and max(raw_scores) > 0 else 1.0

    candidates: List[Dict[str, Any]] = []
    for idx in ranked_indices:
        score = raw_scores[idx]
        if score <= 0.0:
            continue
        p = chunks[idx].copy()
        p["score"] = float(score / max_score)  # Min-max normalized
        p["raw_bm25_score"] = float(score)
        p["retrieval_source"] = "bm25"
        candidates.append(p)

    return candidates

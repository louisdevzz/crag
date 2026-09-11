"""Knowledge Refinement and Multi-Source Evidence Merging Module."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from config import INTERNAL_STRIP_MIN
from legal.parser import split_into_legal_strips
from retrieval.reranker import rerank


def deduplicate_by_locator(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate evidence items by locator, strip_id, or text hash."""
    seen_keys = set()
    unique_items = []

    for item in items:
        # Primary key: locator / strip_id / evidence_id
        key = item.get("strip_id") or item.get("locator") or item.get("evidence_id")
        if not key:
            # Hash text prefix
            text = item.get("text", "").strip()[:100]
            key = re.sub(r"\s+", " ", text.lower())

        if key not in seen_keys:
            seen_keys.add(key)
            unique_items.append(item)

    return unique_items


def refine_internal(
    query: str,
    candidates: List[Dict[str, Any]],
    min_score: float = INTERNAL_STRIP_MIN,
    max_strips: int = 8,
) -> List[Dict[str, Any]]:
    """Decompose candidate passages into atomic legal strips, rerank, and filter out noise.

    Principle (Listing 3.12):
    Never feed long raw passages to Generator. Break into clauses/points,
    rescore relevance, and keep only strips above INTERNAL_STRIP_MIN.
    """
    strips: List[Dict[str, Any]] = []
    for doc in candidates:
        parent_id = doc.get("evidence_id") or doc.get("locator") or "DOC"
        sub_strips = split_into_legal_strips(doc)
        for s in sub_strips:
            s_copy = s.copy()
            s_copy["parent_id"] = parent_id
            s_copy["source_priority"] = doc.get("source_priority", 2)  # Internal = 2
            strips.append(s_copy)

    if not strips:
        return []

    # Rescore all strips against user query
    ranked_strips = rerank(query, strips, top_k=len(strips))

    # Keep only strips that meet the minimum threshold
    refined = [s for s in ranked_strips if s.get("score", 0.0) >= min_score][:max_strips]

    # If all fell below threshold, return top-1 as fallback if candidates existed
    if not refined and ranked_strips:
        refined = [ranked_strips[0]]

    return refined


def refine_external(
    query: str,
    external_docs: List[Dict[str, Any]],
    min_score: float = INTERNAL_STRIP_MIN,
    max_strips: int = 5,
) -> List[Dict[str, Any]]:
    """Refine external crawled web evidence into concise, high-relevance strips."""
    strips: List[Dict[str, Any]] = []
    for doc in external_docs:
        parent_id = doc.get("evidence_id", "EXT")
        sub_strips = split_into_legal_strips(doc)
        for s in sub_strips:
            s_copy = s.copy()
            s_copy["parent_id"] = parent_id
            s_copy["source_priority"] = 1  # External auxiliary = 1
            strips.append(s_copy)

    if not strips:
        return []

    ranked = rerank(query, strips, top_k=len(strips))
    refined = [s for s in ranked if s.get("score", 0.0) >= min_score][:max_strips]
    return refined if refined else ranked[:max_strips]


def merge_evidence(
    internal: List[Dict[str, Any]],
    external: List[Dict[str, Any]],
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    """Merge internal and external evidence with priority ranking (Listing 3.12).

    Priority:
    1. Official Internal Legal Corpus (source_priority = 2)
    2. Controlled External Search (source_priority = 1)
    3. Tie-breaker: Relevance Score
    """
    all_items = internal + external
    unique_items = deduplicate_by_locator(all_items)

    # Sort descending by (source_priority, score)
    merged = sorted(
        unique_items,
        key=lambda x: (x.get("source_priority", 0), x.get("score", 0.0)),
        reverse=True,
    )[:max_items]

    return merged

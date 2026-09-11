"""Reciprocal Rank Fusion (RRF) Module for Hybrid Retrieval."""
from __future__ import annotations

from typing import Any, Dict, List

from config import RRF_K


def rrf_merge(
    result_lists: List[List[Dict[str, Any]]],
    k: int = RRF_K,
    top_k: int = 30,
) -> List[Dict[str, Any]]:
    """Merge ranked candidate lists from multiple retrievers using Reciprocal Rank Fusion.

    Parameters
    ----------
    result_lists : list of list of dict
        Ordered candidate lists, e.g. [dense_candidates, bm25_candidates].
    k : int
        RRF smoothing constant (default: 60).
    top_k : int
        Maximum merged candidates to return.

    Returns
    -------
    list of dict
        Merged candidates sorted by decreasing RRF score.
    """
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}
    sources: Dict[str, List[str]] = {}

    for r_idx, results in enumerate(result_lists):
        for rank, item in enumerate(results, start=1):
            key = item.get("evidence_id") or item.get("locator") or f"ITEM_{rank}"
            score_delta = 1.0 / (k + rank)
            scores[key] = scores.get(key, 0.0) + score_delta

            if key not in items:
                items[key] = item.copy()
                sources[key] = []

            src = item.get("retrieval_source", f"source_{r_idx}")
            if src not in sources[key]:
                sources[key].append(src)

    # Sort descending by fused score
    ordered_keys = sorted(scores.keys(), key=lambda k_id: scores[k_id], reverse=True)[:top_k]

    fused_results: List[Dict[str, Any]] = []
    for k_id in ordered_keys:
        item = items[k_id]
        item["rrf_score"] = float(scores[k_id])
        item["retrieval_sources"] = sources[k_id]
        fused_results.append(item)

    return fused_results

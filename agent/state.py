"""AgentState Definition for Legal CRAG Assistant V3."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """Complete TypedDict state tracking the 3-layer CRAG execution pipeline."""

    # 1. Request & Context
    client_id: str
    session_id: str
    query: str
    as_of_date: Optional[str]        # Target date for temporal validity, e.g. "2026-01-01"
    memory_context: str              # Isolated business background from Semantic Memory
    route: str                       # 'rag' | 'database' | 'general'

    # 2. Retrieval & Evaluator Candidates
    dense_candidates: List[Dict[str, Any]]
    bm25_candidates: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]          # After RRF Fusion and Top-K Rerank
    relevance_scores: List[float]             # Sigmoid-normalized scores [0, 1] from Reranker
    crag_action: str                          # 'CORRECT' | 'AMBIGUOUS' | 'INCORRECT'

    # 3. Evidence Extraction & Merging
    internal_evidence: List[Dict[str, Any]]   # Extracted legal strips from internal corpus
    rewritten_query: str                      # Optimized web search query
    external_evidence: List[Dict[str, Any]]   # Crawled/selected strips from allowed domains
    evidence: List[Dict[str, Any]]            # Unified, deduplicated & prioritized evidence list

    # 4. Generation & Verification Output
    generation: Dict[str, Any]                # {"answer": str, "claims": [...], "abstain": bool}
    citation_report: Dict[str, Any]           # Validation result from CitationValidator
    trace_meta: Dict[str, Any]                # Observability metadata (latency, node trace, etc.)

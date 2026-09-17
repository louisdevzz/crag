"""Dense Semantic Retrieval Module using ChromaDB."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List

from langchain_chroma import Chroma

from config import CHROMA_COLLECTION, CHROMA_DIR, TOP_K_DENSE
from llm import get_embeddings
from logging_config import get_logger, timed_stage

log = get_logger(__name__)

_VECTORSTORE_CACHE: Dict[str, Chroma] = {}
_VECTORSTORE_LOCK = threading.Lock()


def get_vectorstore(chroma_dir: Path | str = CHROMA_DIR) -> Chroma:
    """Cached Chroma collection handle — constructing `Chroma(...)` re-opens the
    persistent client and re-resolves the embedding function, so every distinct
    `chroma_dir` is opened at most once per process and shared by every
    `dense_retrieve` call and the ingestion indexer (same process, `ThreadPoolExecutor`
    background workers), keeping reads consistent with writes."""
    key = str(chroma_dir)
    cached = _VECTORSTORE_CACHE.get(key)
    if cached is not None:
        return cached
    with _VECTORSTORE_LOCK:
        cached = _VECTORSTORE_CACHE.get(key)
        if cached is not None:
            return cached
        instance = Chroma(
            collection_name=CHROMA_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=str(chroma_dir),
        )
        _VECTORSTORE_CACHE[key] = instance
        return instance


def dense_retrieve(
    query: str,
    top_k: int = TOP_K_DENSE,
    chroma_dir: Path | str = CHROMA_DIR,
) -> List[Dict[str, Any]]:
    """Retrieve top-K candidates using dense semantic similarity in ChromaDB.

    Parameters
    ----------
    query : str
        User search query.
    top_k : int
        Number of candidate documents to retrieve (default: 20).

    Returns
    -------
    list of dict
        Candidate records with evidence_id, text, metadata, and similarity score.
    """
    vectorstore = get_vectorstore(chroma_dir)
    with timed_stage(log, "RETRIEVE:DENSE:CHROMA_QUERY", top_k=top_k):
        results_with_scores = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)

    candidates: List[Dict[str, Any]] = []
    for doc, score in results_with_scores:
        meta = doc.metadata or {}
        ev_id = meta.get("evidence_id") or meta.get("locator") or doc.id or f"DENSE_{len(candidates)+1}"
        candidates.append({
            "evidence_id": ev_id,
            "locator": meta.get("locator", ev_id),
            "document_id": meta.get("document_id", ""),
            "document_number": meta.get("document_number", ""),
            "document_title": meta.get("document_title", ""),
            "chapter": meta.get("chapter", ""),
            "article": meta.get("article", ""),
            "clause": meta.get("clause", ""),
            "heading": meta.get("heading", ""),
            "text": doc.page_content,
            "score": float(score) if score is not None else 0.0,
            "retrieval_source": "dense",
            "metadata": meta,
        })

    return candidates

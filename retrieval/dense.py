"""Dense Semantic Retrieval Module using ChromaDB."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from langchain_chroma import Chroma

from config import CHROMA_COLLECTION, CHROMA_DIR, TOP_K_DENSE
from llm import get_embeddings


def get_vectorstore(chroma_dir: Path | str = CHROMA_DIR) -> Chroma:
    """Load the persistent Chroma collection."""
    embeddings = get_embeddings()
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir),
    )


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

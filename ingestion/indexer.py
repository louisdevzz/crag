"""Chroma + BM25 index maintenance, sourced exclusively from `document_chunks` joined
to `documents WHERE status = 'READY'` — the single gate that keeps PROCESSING/FAILED/
UPLOADED documents invisible to CRAG retrieval.
"""
from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rank_bm25 import BM25Okapi

from config import CHROMA_DIR, DB_PATH, PROCESSED_DATA_DIR
from ingestion.documents import get_connection
from ingestion.text import tokenize_vi
from logging_config import get_logger
from retrieval.dense import get_vectorstore

log = get_logger(__name__)


def _ready_chunk_rows(db_path: Path | str = DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as con:
        rows = con.execute(
            """
            SELECT c.id AS evidence_id, c.document_id, c.chapter, c.article, c.clause, c.point,
                   c.heading, c.content AS text, c.page_start, c.page_end,
                   d.document_number, d.title AS document_title
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.status = 'READY'
            """
        ).fetchall()
        return [dict(r) for r in rows]


def rebuild_bm25_index(
    db_path: Path | str = DB_PATH,
    index_path: Path | str = PROCESSED_DATA_DIR / "bm25_index.pkl",
) -> int:
    """Rebuild the BM25 lexical index from every READY document's chunks.

    O(total corpus chunks) — retokenizes everything, not just what changed —
    so a batch/folder upload of N documents must call this once after the
    whole batch (`ingestion.pipeline.run_ingestion_pipeline(..., rebuild_bm25=False)`
    + one final call), never once per document, or it degrades to
    O(N * corpus_size).
    """
    start = time.perf_counter()
    rows = _ready_chunk_rows(db_path)
    for r in rows:
        r["locator"] = r["evidence_id"]
        r["retrieval_source"] = "bm25"

    tokenized_corpus = [tokenize_vi(r["text"] + " " + (r.get("heading") or "")) for r in rows]
    bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else BM25Okapi([[""]])
    bm25_data = {"bm25": bm25, "chunks": rows, "count": len(rows)}

    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "wb") as f:
        pickle.dump(bm25_data, f)

    # Invalidate retrieval/bm25.py's in-process cache so the next query sees this rebuild.
    from retrieval import bm25 as bm25_module
    bm25_module._BM25_CACHE = None

    log.info("[INDEXING] BM25 rebuilt over %d corpus chunk(s) in %.2fs", len(rows), time.perf_counter() - start)
    return len(rows)


def _chunk_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_id": row["evidence_id"],
        "locator": row["evidence_id"],
        "document_id": row["document_id"],
        "document_number": row.get("document_number") or "",
        "document_title": row.get("document_title") or "",
        "chapter": row.get("chapter") or "",
        "article": row.get("article") or "",
        "clause": row.get("clause") or "",
        "heading": row.get("heading") or "",
    }


def index_document_chunks(
    document_id: str,
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> int:
    """(Re-)embed and index every chunk of one document into Chroma. Drops any stale
    vectors for the document first so re-ingestion never duplicates entries.

    `on_progress(done, total)` — when given — fires after each embedding batch so
    a document with hundreds/thousands of chunks shows moving progress instead of
    sitting on "EMBEDDING" for however long the whole document takes.
    """
    remove_document_from_chroma(document_id, chroma_dir=chroma_dir)

    rows = [r for r in _ready_chunk_rows(db_path) if r["document_id"] == document_id]
    if not rows:
        return 0

    vectorstore = get_vectorstore(chroma_dir)
    texts = [r["text"] for r in rows]
    ids = [r["evidence_id"] for r in rows]
    metadatas = [_chunk_metadata(r) for r in rows]

    batch_size = 64
    total = len(texts)
    for i in range(0, total, batch_size):
        batch_start = time.perf_counter()
        vectorstore.add_texts(
            texts=texts[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
            ids=ids[i:i + batch_size],
        )
        done = min(i + batch_size, total)
        log.info(
            "[EMBEDDING] document=%s batch %d-%d/%d done in %.2fs",
            document_id, i + 1, done, total, time.perf_counter() - batch_start,
        )
        if on_progress:
            on_progress(done, total)
    return len(rows)


def remove_document_from_chroma(document_id: str, chroma_dir: Path | str = CHROMA_DIR) -> None:
    """Delete every vector belonging to one document. Lets a real Chroma/DB error
    propagate instead of swallowing it — a caller (document delete, or re-ingestion's
    drop-before-reindex) must see the failure rather than silently leave orphaned
    vectors behind while believing the removal succeeded."""
    vectorstore = get_vectorstore(chroma_dir)
    existing = vectorstore.get(where={"document_id": document_id})
    if existing and existing.get("ids"):
        vectorstore.delete(ids=existing["ids"])

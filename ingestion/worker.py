"""Background execution for the ingestion pipeline: a small thread pool so a document
upload returns immediately while parsing/OCR/embedding run off the request thread.

No external queue/broker: this is a single-node SQLite app, and each pipeline call
opens its own short-lived SQLite connection (WAL + busy_timeout), so a couple of
worker threads never contend with the FastAPI request thread's own connections.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List

from ingestion import indexer
from ingestion.pipeline import run_ingestion_pipeline
from logging_config import get_logger

log = get_logger(__name__)

# How many documents ingest concurrently. Each document's own OCR stage adds
# further internal concurrency (`legal.preprocessor.OCR_CONCURRENCY`), so the
# product of the two is the real ceiling on simultaneous Vision LLM/embedding
# requests — keep this modest by default to avoid tripping provider rate
# limits when a folder upload starts many documents at once.
_WORKER_COUNT = max(1, int(os.getenv("INGESTION_WORKERS", "3")))
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKER_COUNT, thread_name_prefix="ingestion-worker")


def submit_ingestion(document_id: str) -> None:
    future = _EXECUTOR.submit(run_ingestion_pipeline, document_id)

    def _log_result(f):
        exc = f.exception()
        if exc is not None:
            log.error("[INGEST] background worker raised for document=%s: %s", document_id, exc)

    future.add_done_callback(_log_result)


def submit_batch_ingestion(document_ids: List[str]) -> None:
    """Folder/multi-file upload: ingest every document concurrently across the same
    worker pool, each skipping its own BM25 rebuild, then rebuild the corpus BM25
    index exactly once after the whole batch finishes (see
    `ingestion.pipeline.run_ingestion_pipeline`'s `rebuild_bm25` docstring for why
    this matters — one O(corpus_size) rebuild instead of N of them)."""
    log.info("[INGEST:BATCH] submitting %d document(s)", len(document_ids))
    futures = [_EXECUTOR.submit(run_ingestion_pipeline, doc_id, False) for doc_id in document_ids]
    finish_lock = threading.Lock()
    finished = False

    def _finish_batch(_f):
        # Two futures can settle at nearly the same wall-clock instant, each
        # running this callback on its own executor thread — the lock ensures
        # only the callback that actually observes "every future done" first
        # runs the (idempotent but wasteful-to-duplicate) final rebuild.
        nonlocal finished
        if not all(fut.done() for fut in futures):
            return
        with finish_lock:
            if finished:
                return
            finished = True
        for fut in futures:
            exc = fut.exception()
            if exc is not None:
                log.error("[INGEST:BATCH] a document failed: %s", exc)
        try:
            total = indexer.rebuild_bm25_index()
            log.info("[INGEST:BATCH] finished %d document(s) -> BM25 rebuilt (%d corpus chunks)", len(document_ids), total)
        except Exception:
            log.exception("[INGEST:BATCH] final BM25 rebuild failed")

    for fut in futures:
        fut.add_done_callback(_finish_batch)

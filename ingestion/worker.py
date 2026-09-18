"""Background thread pool worker for the document ingestion pipeline."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List

from ingestion import indexer
from ingestion.pipeline import run_ingestion_pipeline
from logging_config import get_logger

log = get_logger(__name__)

# Maximum concurrent document ingestion workers.
_WORKER_COUNT = max(1, int(os.getenv("INGESTION_WORKERS", "3")))
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKER_COUNT, thread_name_prefix="ingestion-worker")


def submit_ingestion(document_id: str) -> None:
    """Submit a single document for background ingestion."""
    future = _EXECUTOR.submit(run_ingestion_pipeline, document_id)

    def _log_result(f):
        exc = f.exception()
        if exc is not None:
            log.error("[INGEST] background worker raised for document=%s: %s", document_id, exc)

    future.add_done_callback(_log_result)


def submit_batch_ingestion(document_ids: List[str]) -> None:
    """Submit multiple documents for concurrent ingestion and rebuild BM25 index once completed."""
    log.info("[INGEST:BATCH] submitting %d document(s)", len(document_ids))
    futures = [_EXECUTOR.submit(run_ingestion_pipeline, doc_id, False) for doc_id in document_ids]
    finish_lock = threading.Lock()
    finished = False

    def _finish_batch(_f):
        # Lock ensures only the first completed callback runs final BM25 rebuild.
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

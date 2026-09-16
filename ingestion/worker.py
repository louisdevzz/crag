"""Background execution for the ingestion pipeline: a small thread pool so a document
upload returns immediately while parsing/OCR/embedding run off the request thread.

No external queue/broker: this is a single-node SQLite app, and each pipeline call
opens its own short-lived SQLite connection (WAL + busy_timeout), so a couple of
worker threads never contend with the FastAPI request thread's own connections.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ingestion.pipeline import run_ingestion_pipeline
from logging_config import get_logger

log = get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingestion-worker")


def submit_ingestion(document_id: str) -> None:
    future = _EXECUTOR.submit(run_ingestion_pipeline, document_id)

    def _log_result(f):
        exc = f.exception()
        if exc is not None:
            log.error("[INGEST] background worker raised for document=%s: %s", document_id, exc)

    future.add_done_callback(_log_result)

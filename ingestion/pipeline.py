"""Staged ingestion pipeline orchestration: PARSING -> [OCR] -> CLEANING ->
STRUCTURING -> CHUNKING -> EMBEDDING -> INDEXING -> READY. Each stage updates
the document's `ingestion_jobs` row (coarse `stage`/`progress` plus a
fine-grained `detail`/`processed_units`/`total_units` that moves *within* a
stage — "OCR trang 12/45", "Đang nhúng đoạn 320/1200") so the Admin UI can
render a live processing checklist that keeps moving even on a large
multi-page document, and every stage/sub-step is timed to the console via
`logging_config.timed_stage` for diagnosing exactly where time goes.

Runs on a background worker thread (see `ingestion.worker`); a failure at any stage
flips `documents.status` to FAILED with `error_message` set and leaves no partial
vectors behind.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf

from ingestion import chunks as chunks_repo
from ingestion import documents as documents_repo
from ingestion import indexer
from ingestion import jobs as jobs_repo
from legal.cleaner import clean_pages
from legal.parser import parse_legal_document
from legal.preprocessor import UniversalLegalPreprocessor
from logging_config import get_logger, timed_stage

log = get_logger(__name__)


def _needs_ocr(pdf_path: Path) -> bool:
    """True when at least one page lacks a digital text layer (checked up front so the
    OCR stage can be reported *before* the per-page Vision LLM calls actually run)."""
    doc = pymupdf.open(pdf_path)
    try:
        return any(len(doc[i].get_text("text").strip()) <= 50 for i in range(len(doc)))
    finally:
        doc.close()


def _extract_text(file_path: Path, job_id: str) -> Tuple[str, List[Dict[str, Any]]]:
    preprocessor = UniversalLegalPreprocessor(enable_vision_ocr=True)
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        if _needs_ocr(file_path):
            jobs_repo.update_stage(job_id, "OCR")

            def on_ocr_progress(done: int, total: int) -> None:
                jobs_repo.update_progress(job_id, detail=f"OCR trang {done}/{total}", processed=done, total=total)

            with timed_stage(log, "INGEST:OCR", document=file_path.name):
                return preprocessor.extract_text_from_pdf(file_path, on_ocr_progress=on_ocr_progress)
        with timed_stage(log, "INGEST:PARSING", document=file_path.name):
            return preprocessor.extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        with timed_stage(log, "INGEST:PARSING", document=file_path.name):
            raw_text = preprocessor._extract_text_from_docx(file_path)
        return raw_text, [{"page_number": 1, "text": raw_text, "source_type": "docx"}]
    elif ext in (".txt", ".md", ".html"):
        raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
        return raw_text, [{"page_number": 1, "text": raw_text, "source_type": "text"}]
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def run_ingestion_pipeline(document_id: str, rebuild_bm25: bool = True) -> None:
    """Execute the full staged pipeline for one already-created `documents` row.

    `rebuild_bm25=False` — used by `ingestion.worker.submit_batch_ingestion` for a
    folder/multi-file upload — skips the corpus-wide BM25 rebuild here; the caller
    rebuilds it exactly once after every document in the batch has finished, instead
    of once per document (rebuilding tokenizes every READY chunk in the whole
    corpus, so doing it N times for an N-file batch is O(N * corpus_size) instead
    of O(corpus_size)).
    """
    job = jobs_repo.get_job_for_document(document_id)
    if job is None:
        raise RuntimeError(f"No ingestion job found for document {document_id}")
    job_id = job["id"]

    doc = documents_repo.get_document(document_id)
    if doc is None:
        raise RuntimeError(f"Document not found: {document_id}")

    try:
        documents_repo.update_document(document_id, status="PROCESSING")
        jobs_repo.update_stage(job_id, "PARSING")

        file_path = Path(doc["file_path"])
        raw_text, pages_data = _extract_text(file_path, job_id)

        jobs_repo.update_stage(job_id, "CLEANING")
        with timed_stage(log, "INGEST:CLEANING", document=file_path.name):
            raw_text, pages_data = clean_pages(pages_data)

        jobs_repo.update_stage(job_id, "STRUCTURING")
        with timed_stage(log, "INGEST:STRUCTURING", document=file_path.name):
            preprocessor = UniversalLegalPreprocessor(enable_vision_ocr=False)
            metadata = preprocessor.extract_metadata(raw_text, file_path)
            provisions = parse_legal_document(raw_text, metadata, pages_data=pages_data)

        jobs_repo.update_stage(job_id, "CHUNKING")
        with timed_stage(log, "INGEST:CHUNKING", document=file_path.name, provisions=len(provisions)):
            chunk_count = chunks_repo.replace_chunks(document_id, provisions)

        documents_repo.update_document(
            document_id,
            document_number=metadata.get("document_number"),
            title=metadata.get("title"),
            document_type=metadata.get("document_type"),
            issuing_authority=metadata.get("issuing_authority"),
            issued_at=metadata.get("issued_at"),
            effective_from=metadata.get("effective_from"),
            effective_to=metadata.get("effective_to"),
            legal_status=metadata.get("status", "effective"),
            source_url=metadata.get("source_url"),
            page_count=len(pages_data),
            chunk_count=chunk_count,
        )

        # A document must be READY before it is visible to `ingestion.indexer`'s
        # `WHERE d.status = 'READY'` gate, so flip status ahead of the embed/index calls.
        documents_repo.update_document(document_id, status="READY")

        jobs_repo.update_stage(job_id, "EMBEDDING")

        def on_embed_progress(done: int, total: int) -> None:
            jobs_repo.update_progress(job_id, detail=f"Đang nhúng đoạn {done}/{total}", processed=done, total=total)

        with timed_stage(log, "INGEST:EMBEDDING", document=file_path.name, chunks=chunk_count):
            indexer.index_document_chunks(document_id, on_progress=on_embed_progress)

        if rebuild_bm25:
            jobs_repo.update_stage(job_id, "INDEXING")
            with timed_stage(log, "INGEST:INDEXING", document=file_path.name):
                indexer.rebuild_bm25_index()

        jobs_repo.finish_job(job_id)
        log.info("[INGEST] document=%s chunks=%d -> READY", document_id, chunk_count)

    except Exception as e:
        log.exception("[INGEST] document=%s FAILED", document_id)
        # Never leave partial vectors behind for a document that isn't READY.
        try:
            indexer.remove_document_from_chroma(document_id)
            if rebuild_bm25:
                indexer.rebuild_bm25_index()
        except Exception:
            log.exception("[INGEST] cleanup after failure also failed for document=%s", document_id)
        documents_repo.update_document(document_id, status="FAILED", error_message=str(e))
        jobs_repo.finish_job(job_id, error_message=str(e))

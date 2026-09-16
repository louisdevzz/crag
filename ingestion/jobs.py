"""Ingestion job tracking (`ingestion_jobs` table): one row per upload, polled by
the Admin UI to render the processing checklist.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from config import DB_PATH
from ingestion.documents import get_connection

# Stage order mirrors the real pipeline steps in `ingestion.pipeline.run_ingestion_pipeline`.
# OCR is skipped (never reported) for documents whose PDF pages all carry a digital text layer.
STAGES = ["PARSING", "OCR", "STRUCTURING", "CHUNKING", "EMBEDDING", "INDEXING", "DONE"]

STAGE_PROGRESS: Dict[str, float] = {
    "PARSING": 10.0,
    "OCR": 25.0,
    "STRUCTURING": 45.0,
    "CHUNKING": 60.0,
    "EMBEDDING": 80.0,
    "INDEXING": 95.0,
    "DONE": 100.0,
    "FAILED": 100.0,
}


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


def create_job(document_id: str, db_path: Path | str = DB_PATH) -> Dict[str, Any]:
    job_id = new_job_id()
    with get_connection(db_path) as con:
        con.execute(
            "INSERT INTO ingestion_jobs (id, document_id, stage, progress) VALUES (?, ?, 'PARSING', ?)",
            (job_id, document_id, STAGE_PROGRESS["PARSING"]),
        )
        con.commit()
    return get_job(job_id, db_path=db_path)


def update_stage(job_id: str, stage: str, db_path: Path | str = DB_PATH) -> None:
    progress = STAGE_PROGRESS.get(stage, 0.0)
    with get_connection(db_path) as con:
        con.execute(
            "UPDATE ingestion_jobs SET stage = ?, progress = ? WHERE id = ?",
            (stage, progress, job_id),
        )
        con.commit()


def finish_job(job_id: str, error_message: Optional[str] = None, db_path: Path | str = DB_PATH) -> None:
    stage = "FAILED" if error_message else "DONE"
    with get_connection(db_path) as con:
        con.execute(
            """
            UPDATE ingestion_jobs
            SET stage = ?, progress = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (stage, STAGE_PROGRESS[stage], error_message, job_id),
        )
        con.commit()


def get_job(job_id: str, db_path: Path | str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as con:
        row = con.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_job_for_document(document_id: str, db_path: Path | str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Latest job row for a document (one document may be re-ingested via `replace=true`)."""
    with get_connection(db_path) as con:
        row = con.execute(
            "SELECT * FROM ingestion_jobs WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
            (document_id,),
        ).fetchone()
        return dict(row) if row else None

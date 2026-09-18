"""Documents CRUD operations for the corpus catalog database."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DB_PATH


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        from create_db import init_db
        init_db(path, quiet=True)
    con = sqlite3.connect(str(path), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def new_document_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


def create_document(
    filename: str,
    file_path: str,
    file_type: str,
    content_hash: str,
    document_id: Optional[str] = None,
    db_path: Path | str = DB_PATH,
) -> Dict[str, Any]:
    """Insert a freshly-uploaded document row (status=UPLOADED, no metadata yet)."""
    doc_id = document_id or new_document_id()
    with get_connection(db_path) as con:
        con.execute(
            """
            INSERT INTO documents (id, filename, title, file_path, file_type, content_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, 'UPLOADED')
            """,
            (doc_id, filename, filename, file_path, file_type, content_hash),
        )
        con.commit()
    return get_document(doc_id, db_path=db_path)


def find_by_content_hash(content_hash: str, db_path: Path | str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as con:
        row = con.execute(
            "SELECT * FROM documents WHERE content_hash = ? ORDER BY created_at DESC LIMIT 1",
            (content_hash,),
        ).fetchone()
        return dict(row) if row else None


def get_document(document_id: str, db_path: Path | str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as con:
        row = con.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return dict(row) if row else None


_UPDATABLE_COLUMNS = {
    "filename", "document_number", "title", "document_type", "issuing_authority",
    "issued_at", "effective_from", "effective_to", "status", "legal_status", "source_url",
    "file_path", "file_type", "content_hash", "page_count", "chunk_count", "error_message",
}


def update_document(document_id: str, db_path: Path | str = DB_PATH, **fields: Any) -> None:
    """Patch arbitrary allowed columns on a document row and bump `updated_at`."""
    cols = {k: v for k, v in fields.items() if k in _UPDATABLE_COLUMNS}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = ?" for k in cols) + ", updated_at = CURRENT_TIMESTAMP"
    with get_connection(db_path) as con:
        con.execute(
            f"UPDATE documents SET {set_clause} WHERE id = ?",
            (*cols.values(), document_id),
        )
        con.commit()


def list_documents(db_path: Path | str = DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as con:
        rows = con.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_document(document_id: str, db_path: Path | str = DB_PATH) -> Dict[str, Any]:
    """Delete a document row (cascades to document_chunks/ingestion_jobs via FK)."""
    doc = get_document(document_id, db_path=db_path)
    if doc is None:
        raise KeyError(f"Document not found: {document_id}")
    with get_connection(db_path) as con:
        con.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        con.commit()
    return doc

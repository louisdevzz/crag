"""Document chunk persistence: the indexed retrieval unit (`document_chunks` table).

One chunk per legal provision (Chương -> Điều -> Khoản) produced by
`legal.parser.parse_legal_document`, at the granularity CRAG retrieval and the
Admin chunk browser both operate on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DB_PATH
from ingestion.documents import get_connection


def replace_chunks(document_id: str, provisions: List[Dict[str, Any]], db_path: Path | str = DB_PATH) -> int:
    """Replace every chunk of `document_id` with the freshly parsed `provisions` list."""
    with get_connection(db_path) as con:
        con.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
        for idx, p in enumerate(provisions):
            chunk_id = p.get("id") or p.get("locator") or f"{document_id}_c{idx:04d}"
            content = p.get("text", "")
            con.execute(
                """
                INSERT OR REPLACE INTO document_chunks (
                    id, document_id, chunk_index, chapter, article, clause, point,
                    heading, page_start, page_end, content, token_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id, document_id, idx,
                    p.get("chapter", ""), p.get("article", ""), p.get("clause", ""), p.get("point", ""),
                    p.get("heading", ""), p.get("page_start"), p.get("page_end"),
                    content, len(content.split()) if content else 0,
                ),
            )
        con.commit()
    return len(provisions)


def list_chunks(document_id: str, db_path: Path | str = DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as con:
        rows = con.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index ASC",
            (document_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_chunk(chunk_id: str, db_path: Path | str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as con:
        row = con.execute("SELECT * FROM document_chunks WHERE id = ?", (chunk_id,)).fetchone()
        return dict(row) if row else None


def count_chunks(document_id: str, db_path: Path | str = DB_PATH) -> int:
    with get_connection(db_path) as con:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM document_chunks WHERE document_id = ?", (document_id,)
        ).fetchone()
        return row["n"] if row else 0

"""Database Tool for Structured Legal Metadata Queries.

Modeled after Hermes Agent tool architecture.
Provides Pydantic-validated arguments and structured relation exploration.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import DB_PATH
from legal.temporal import is_effective_at
from tools.base import BaseLegalTool


def get_connection(db_path: str = str(DB_PATH)) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        from create_db import init_db
        init_db(path, quiet=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con

class DatabaseQueryInput(BaseModel):
    """Schema for legal database metadata query arguments."""
    query: str = Field(..., description="Natural language question or search query")
    document_number: Optional[str] = Field(None, description="Specific document number if known, e.g. '41/2024/QH15'")
    as_of_date: Optional[str] = Field(None, description="Reference date for temporal validity check (YYYY-MM-DD)")


class DatabaseTool(BaseLegalTool):
    """Tool for querying structured legal document catalogs, validity, and relations."""

    name: str = "database_query"
    description: str = "Tra cứu thông tin có cấu trúc của văn bản pháp luật: số hiệu, cơ quan ban hành, ngày có hiệu lực, và quan hệ sửa đổi/thay thế."
    args_schema = DatabaseQueryInput

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path

    def execute(
        self,
        query: str,
        document_number: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute structured SQLite lookup."""
        doc_num = document_number or (extract_document_numbers(query)[0] if extract_document_numbers(query) else None)

        if doc_num:
            info = query_document_status(doc_num, as_of_date=as_of_date, db_path=self.db_path)
            if info:
                relations = query_document_relations(info["id"], db_path=self.db_path)
                info["relations"] = relations
                return {
                    "query": query,
                    "matched_by": "document_number",
                    "found_documents": [info],
                    "count": 1,
                }

        # Fallback to search by title / keyword
        return handle_database_query(query, as_of_date=as_of_date, db_path=self.db_path)


def extract_document_numbers(query: str) -> List[str]:
    """Extract Vietnamese legal document numbers using flexible regex patterns."""
    pattern = re.compile(r"\b\d{1,4}/\d{4}/(?:[A-ZĐa-zđ0-9\-_]+)\b")
    matches = pattern.findall(query)
    if not matches:
        alt_pattern = re.compile(
            r"(?:Luật|Nghị định|Thông tư|Bộ luật|Quyết định)\s+(?:số\s+)?(\d{1,4}/\d{4}/[A-ZĐa-zđ0-9\-_]+)",
            re.IGNORECASE,
        )
        matches = [m.group(1) for m in alt_pattern.finditer(query)]
    return list(set(matches))


def query_document_status(
    document_number: str,
    as_of_date: Optional[str] = None,
    db_path: str = str(DB_PATH),
) -> Optional[Dict[str, Any]]:
    """Query the status, effective dates, and authority for a specific legal document."""
    doc_clean = document_number.strip()
    with get_connection(db_path) as con:
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, document_number, title, document_type, issuing_authority,
                   issued_at, effective_from, effective_to, status, source_url
            FROM legal_documents
            WHERE document_number = ? OR document_number LIKE ?
            LIMIT 1
            """,
            (doc_clean, f"%{doc_clean}%"),
        )
        row = cur.fetchone()
        if not row:
            return None

        data = dict(row)
        data["is_effective_now"] = is_effective_at(data, as_of_date)
        return data


def query_document_relations(
    document_id_or_number: str,
    db_path: str = str(DB_PATH),
) -> List[Dict[str, Any]]:
    """Query amending, replacing, or guiding relationships for a legal document."""
    with get_connection(db_path) as con:
        cur = con.cursor()
        cur.execute(
            """
            SELECT r.id, r.relation_type, r.note,
                   sd.document_number as source_number, sd.title as source_title,
                   td.document_number as target_number, td.title as target_title
            FROM legal_relations r
            JOIN legal_documents sd ON r.source_document_id = sd.id
            JOIN legal_documents td ON r.target_document_id = td.id
            WHERE sd.document_number = ? OR td.document_number = ?
               OR sd.id = ? OR td.id = ?
            """,
            (document_id_or_number, document_id_or_number, document_id_or_number, document_id_or_number),
        )
        return [dict(r) for r in cur.fetchall()]


def handle_database_query(
    query: str,
    as_of_date: Optional[str] = None,
    db_path: str = str(DB_PATH),
) -> Dict[str, Any]:
    """Top-level handler for database query routing."""
    doc_numbers = extract_document_numbers(query)
    results = []

    for doc_num in doc_numbers:
        info = query_document_status(doc_num, as_of_date, db_path=db_path)
        if info:
            relations = query_document_relations(info["id"], db_path=db_path)
            info["relations"] = relations
            results.append(info)

    if not results:
        with get_connection(db_path) as con:
            cur = con.cursor()
            words = [w for w in query.split() if len(w) > 2]
            for w in words[:3]:
                cur.execute(
                    "SELECT * FROM legal_documents WHERE title LIKE ? LIMIT 3",
                    (f"%{w}%",),
                )
                for r in cur.fetchall():
                    d = dict(r)
                    d["is_effective_now"] = is_effective_at(d, as_of_date)
                    if d not in results:
                        results.append(d)

    return {
        "query": query,
        "document_numbers_detected": doc_numbers,
        "found_documents": results,
        "count": len(results),
    }

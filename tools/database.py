"""Database Tool for Structured Legal Metadata Queries."""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List, Optional

from config import DB_PATH
from legal.temporal import is_effective_at


def get_connection(db_path: str = str(DB_PATH)) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def extract_document_numbers(query: str) -> List[str]:
    """Extract Vietnamese legal document numbers using regex patterns.

    Examples: 01/2021/NĐ-CP, 59/2020/QH14, 45/2019/QH14, 145/2020/NĐ-CP.
    """
    pattern = re.compile(r"\b\d{1,4}/\d{4}/(?:[A-ZĐa-zđ0-9\-_]+)\b")
    matches = pattern.findall(query)
    # Also check without leading zero or specific terms
    if not matches:
        alt_pattern = re.compile(r"(?:Luật|Nghị định|Thông tư|Bộ luật)\s+(?:số\s+)?(\d{1,4}/\d{4}/[A-ZĐa-zđ0-9\-_]+)", re.IGNORECASE)
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
        # Search by exact number or LIKE match
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


def handle_database_query(query: str, as_of_date: Optional[str] = None, db_path: str = str(DB_PATH)) -> Dict[str, Any]:
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
        # Fallback keyword search on titles
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

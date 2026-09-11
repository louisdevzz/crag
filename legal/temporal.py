"""Temporal Validity and Hierarchy Checker for Vietnamese Legal Documents."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional


LEGAL_HIERARCHY_RANK = {
    "HIẾN PHÁP": 100,
    "BỘ LUẬT": 90,
    "LUẬT": 80,
    "NGHỊ QUYẾT": 70,
    "NGHỊ ĐỊNH": 60,
    "QUYẾT ĐỊNH": 50,
    "THÔNG TƯ": 40,
    "THÔNG TƯ LIÊN TỊCH": 35,
}


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string in various formats into datetime.date."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_effective_at(doc_meta: Dict[str, Any], as_of_date_str: Optional[str] = None) -> bool:
    """Check if a legal document or provision is in effect on a given reference date.

    Parameters
    ----------
    doc_meta : dict
        Metadata containing 'effective_from', 'effective_to', and 'status'.
    as_of_date_str : str, optional
        Target reference date (default: today or 2026-01-01).

    Returns
    -------
    bool
        True if the document is active and valid on as_of_date, False otherwise.
    """
    status = str(doc_meta.get("status", "")).lower().strip()
    if status == "expired" or status == "hethieuluc":
        return False

    if not as_of_date_str:
        return status in ("effective", "conhieuluc", "")

    target_date = parse_date(as_of_date_str)
    if not target_date:
        return True

    effective_from = parse_date(doc_meta.get("effective_from"))
    effective_to = parse_date(doc_meta.get("effective_to"))

    if effective_from and target_date < effective_from:
        # Not yet effective
        return False

    if effective_to and target_date > effective_to:
        # Already expired
        return False

    return True


def get_document_rank(doc_type_or_title: str) -> int:
    """Determine normative hierarchy rank from document type or title."""
    s = doc_type_or_title.upper()
    for key, rank in LEGAL_HIERARCHY_RANK.items():
        if key in s:
            return rank
    return 10


def resolve_legal_conflict(doc_a: Dict[str, Any], doc_b: Dict[str, Any], as_of_date: Optional[str] = None) -> Dict[str, Any]:
    """Resolve conflict between two legal documents based on hierarchy and temporal validity.

    Rules:
    1. Only effective documents at as_of_date are considered.
    2. Higher normative rank prevails (e.g. Luật > Nghị định).
    3. If same rank, newer document (effective_from) prevails (Lex posterior derogat legi priori).
    """
    eff_a = is_effective_at(doc_a, as_of_date)
    eff_b = is_effective_at(doc_b, as_of_date)

    if eff_a and not eff_b:
        return {"winner": doc_a, "reason": f"{doc_b.get('document_number')} đã hết hiệu lực tại ngày {as_of_date}"}
    if eff_b and not eff_a:
        return {"winner": doc_b, "reason": f"{doc_a.get('document_number')} đã hết hiệu lực tại ngày {as_of_date}"}

    rank_a = get_document_rank(doc_a.get("document_type", "") or doc_a.get("title", ""))
    rank_b = get_document_rank(doc_b.get("document_type", "") or doc_b.get("title", ""))

    if rank_a > rank_b:
        return {"winner": doc_a, "reason": f"Thứ bậc pháp lý cao hơn ({doc_a.get('document_type')} > {doc_b.get('document_type')})"}
    if rank_b > rank_a:
        return {"winner": doc_b, "reason": f"Thứ bậc pháp lý cao hơn ({doc_b.get('document_type')} > {doc_a.get('document_type')})"}

    # Same rank: check effective_from
    date_a = parse_date(doc_a.get("effective_from")) or date.min
    date_b = parse_date(doc_b.get("effective_from")) or date.min

    if date_a >= date_b:
        return {"winner": doc_a, "reason": "Văn bản ban hành sau (nguyên tắc Lex Posterior)"}
    else:
        return {"winner": doc_b, "reason": "Văn bản ban hành sau (nguyên tắc Lex Posterior)"}

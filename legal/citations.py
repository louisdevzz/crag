"""Deterministic Citation Validator for Legal Answers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from legal.temporal import is_effective_at


def validate_citations(
    answer: Dict[str, Any],
    evidence_map: Dict[str, Dict[str, Any]],
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate citations in LLM answer against retrieved legal evidence.

    Ensures:
    1. Every cited source_id exists in the provided evidence map.
    2. The referenced legal document is in effect as of the reference date.
    3. Computes Citation Accuracy and Citation Coverage metrics.

    Parameters
    ----------
    answer : dict
        LLM generation output with format:
        {"answer": str, "claims": [{"text": str, "source_ids": list[str]}], "abstain": bool}
    evidence_map : dict
        Mapping from evidence_id / locator to evidence dict.
    as_of_date : str, optional
        Reference date (YYYY-MM-DD) to test temporal validity.

    Returns
    -------
    dict
        Validation report with {"ok": bool, "errors": list[str], "valid_citations": list[str], ...}
    """
    errors: List[str] = []
    valid_citations: List[str] = []
    total_cited = 0
    claims = answer.get("claims", [])
    claims_with_valid_citation = 0

    # Build locator lookup with prefix support
    known_keys = set(evidence_map.keys())

    def find_evidence_match(sid: str) -> Optional[Dict[str, Any]]:
        if sid in evidence_map:
            return evidence_map[sid]
        # Check prefix / parent locator
        for k in known_keys:
            if sid.startswith(k) or k.startswith(sid):
                return evidence_map[k]
        return None

    for claim_idx, claim in enumerate(claims, start=1):
        claim_text = claim.get("text", "")
        source_ids = claim.get("source_ids", [])
        has_valid_for_claim = False

        for sid in source_ids:
            total_cited += 1
            ev = find_evidence_match(sid)
            if not ev:
                errors.append(
                    f"Mệnh đề #{claim_idx} ('{claim_text[:50]}...'): "
                    f"source_id không tồn tại trong danh mục bằng chứng: '{sid}'"
                )
                continue

            # Temporal validity check
            meta = ev.get("metadata", ev)
            if as_of_date and not is_effective_at(meta, as_of_date):
                doc_num = meta.get("document_number") or sid
                errors.append(
                    f"Mệnh đề #{claim_idx}: Văn bản trích dẫn '{doc_num}' "
                    f"không còn hiệu lực tại ngày tham chiếu {as_of_date}"
                )
                continue

            valid_citations.append(sid)
            has_valid_for_claim = True

        if has_valid_for_claim:
            claims_with_valid_citation += 1

    total_claims = len(claims)
    accuracy = (len(valid_citations) / total_cited) if total_cited > 0 else (1.0 if answer.get("abstain") else 0.0)
    coverage = (claims_with_valid_citation / total_claims) if total_claims > 0 else 1.0

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "valid_citations": valid_citations,
        "total_citations": total_cited,
        "total_claims": total_claims,
        "claims_with_valid_citation": claims_with_valid_citation,
        "citation_accuracy": round(accuracy, 4),
        "citation_coverage": round(coverage, 4),
    }

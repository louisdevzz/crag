"""Legal Document Parser with Hierarchical Chunking (Legal-aware Chunking).

Breaks down Vietnamese normative legal documents following the hierarchical structure:
Văn bản -> Chương -> Điều -> Khoản -> Điểm.
Preserves provenance and deterministic locators for citation validation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


CHAPTER_PATTERN = re.compile(
    r"^(Chương\s+[IVXLCDM\d]+|Mục\s+\d+|Phần\s+[IVXLCDM\d]+)[\.:\s]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
ARTICLE_PATTERN = re.compile(
    r"^(Điều\s+\d+)[\.:\s]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
CLAUSE_PATTERN = re.compile(
    r"^(\d+)\.\s+(.*)$",
    re.MULTILINE,
)
POINT_PATTERN = re.compile(
    r"^([a-zđ])\)\s+(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_legal_document(
    raw_text: str,
    doc_metadata: Dict[str, Any],
    pages_data: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Parse raw Vietnamese legal document text into structured provisions.

    Parameters
    ----------
    raw_text : str
        Full text or section text of the legal document. Used verbatim when
        `pages_data` is not supplied.
    doc_metadata : dict
        Document metadata (id, document_number, title, etc.)
    pages_data : list of dict, optional
        Per-page records `{"page_number": int, "text": str, ...}` as returned by
        `UniversalLegalPreprocessor.extract_text_from_pdf`. When supplied, each
        emitted provision is tagged with the page range its source lines came
        from (`page_start`/`page_end`); otherwise both are `None`.

    Returns
    -------
    list of dict
        Structured provision chunks ready for database storage and indexing.
    """
    doc_id = doc_metadata.get("id", "DOC")
    doc_number = doc_metadata.get("document_number", "")
    doc_title = doc_metadata.get("title", "")

    if pages_data:
        lines: List[str] = []
        line_pages: List[Optional[int]] = []
        for page in pages_data:
            page_lines = page.get("text", "").split("\n")
            lines.extend(page_lines)
            line_pages.extend([page.get("page_number")] * len(page_lines))
    else:
        lines = raw_text.split("\n")
        line_pages = [None] * len(lines)

    provisions: List[Dict[str, Any]] = []
    seen_ids: Dict[str, int] = {}

    def make_unique_id(base_id: str) -> str:
        count = seen_ids.get(base_id, 0) + 1
        seen_ids[base_id] = count
        return base_id if count == 1 else f"{base_id}_{count}"

    current_chapter = ""
    current_chapter_title = ""
    current_article = ""
    current_article_title = ""
    current_article_lines: List[str] = []
    current_article_page_start: Optional[int] = None
    current_article_page_end: Optional[int] = None

    def flush_article():
        nonlocal current_article_lines, current_article_page_start, current_article_page_end
        if not current_article or not current_article_lines:
            current_article_page_start = None
            current_article_page_end = None
            return

        article_text = "\n".join(current_article_lines).strip()
        art_match = re.search(r"\d+", current_article)
        art_num = art_match.group(0) if art_match else current_article
        page_start = current_article_page_start
        page_end = current_article_page_end

        # Decompose into clauses if present
        clauses = split_clauses(article_text)
        if clauses:
            for c_num, c_text in clauses:
                base_id = f"{doc_id}_D{art_num}_K{c_num}" if c_num else f"{doc_id}_D{art_num}"
                prov_id = make_unique_id(base_id)
                heading = current_article_title or f"{current_article}"
                breadcrumb = f"{doc_title} > {current_chapter} > {current_article}"
                if c_num:
                    breadcrumb += f" > Khoản {c_num}"

                provisions.append({
                    "id": prov_id,
                    "document_id": doc_id,
                    "document_number": doc_number,
                    "chapter": current_chapter,
                    "article": current_article,
                    "clause": f"Khoản {c_num}" if c_num else "",
                    "point": "",
                    "heading": heading,
                    "text": c_text,
                    "locator": prov_id,
                    "provenance": breadcrumb,
                    "page_start": page_start,
                    "page_end": page_end,
                    "metadata": {
                        "document_id": doc_id,
                        "document_number": doc_number,
                        "document_title": doc_title,
                        "chapter": current_chapter,
                        "article": current_article,
                        "clause": f"Khoản {c_num}" if c_num else "",
                        "locator": prov_id,
                    }
                })
        else:
            base_id = f"{doc_id}_D{art_num}"
            prov_id = make_unique_id(base_id)
            breadcrumb = f"{doc_title} > {current_chapter} > {current_article}"
            provisions.append({
                "id": prov_id,
                "document_id": doc_id,
                "document_number": doc_number,
                "chapter": current_chapter,
                "article": current_article,
                "clause": "",
                "point": "",
                "heading": current_article_title or current_article,
                "text": article_text,
                "locator": prov_id,
                "provenance": breadcrumb,
                "page_start": page_start,
                "page_end": page_end,
                "metadata": {
                    "document_id": doc_id,
                    "document_number": doc_number,
                    "document_title": doc_title,
                    "chapter": current_chapter,
                    "article": current_article,
                    "clause": "",
                    "locator": prov_id,
                }
            })

        current_article_lines = []
        current_article_page_start = None
        current_article_page_end = None

    for line, page_num in zip(lines, line_pages):
        stripped = line.strip()
        if not stripped:
            continue

        # Check Chapter / Part heading
        ch_match = CHAPTER_PATTERN.match(stripped)
        if ch_match:
            flush_article()
            current_chapter = ch_match.group(1).strip()
            current_chapter_title = ch_match.group(2).strip()
            continue

        # Check Article heading
        art_match = ARTICLE_PATTERN.match(stripped)
        if art_match:
            flush_article()
            current_article = art_match.group(1).strip()
            current_article_title = art_match.group(2).strip()
            current_article_page_start = page_num
            current_article_page_end = page_num
            continue

        if current_article:
            current_article_lines.append(stripped)
            if page_num is not None:
                if current_article_page_start is None:
                    current_article_page_start = page_num
                current_article_page_end = page_num

    # Flush last article
    flush_article()
    return provisions


def split_clauses(article_text: str) -> List[tuple[str, str]]:
    """Split article text into numbered clauses (Khoản 1, Khoản 2, ...)."""
    lines = article_text.split("\n")
    clauses: List[tuple[str, str]] = []
    current_clause_num = ""
    current_clause_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            if current_clause_lines:
                clauses.append((current_clause_num, "\n".join(current_clause_lines).strip()))
                current_clause_lines = []
            current_clause_num = m.group(1)
            current_clause_lines.append(m.group(2).strip())
        else:
            if current_clause_num:
                current_clause_lines.append(stripped)
            else:
                # Text preceding clause 1 (preamble or lead-in)
                current_clause_lines.append(stripped)

    if current_clause_lines:
        clauses.append((current_clause_num, "\n".join(current_clause_lines).strip()))

    return clauses


def split_into_legal_strips(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Decompose a provision chunk into atomic legal strips (Khoản / Điểm).

    Used in Step 11-14: Knowledge Refinement to score and extract only relevant strips.
    """
    text = doc.get("text", "")
    locator = doc.get("locator") or doc.get("id") or doc.get("evidence_id", "E")
    heading = doc.get("heading", "")
    metadata = doc.get("metadata", {})

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    strips: List[Dict[str, Any]] = []

    # Check if text contains multiple sub-points: a), b), c) or sentences
    point_regex = re.compile(r"^([a-zđ])\)\s+(.*)$", re.IGNORECASE)
    current_point = ""
    current_lines: List[str] = []

    for line in lines:
        m = point_regex.match(line)
        if m:
            if current_lines:
                strip_id = f"{locator}_{current_point}" if current_point else locator
                strips.append({
                    "strip_id": strip_id,
                    "evidence_id": locator,
                    "heading": heading,
                    "text": " ".join(current_lines),
                    "locator": strip_id,
                    "metadata": metadata,
                })
                current_lines = []
            current_point = m.group(1).lower()
            current_lines.append(m.group(2))
        else:
            current_lines.append(line)

    if current_lines:
        strip_id = f"{locator}_{current_point}" if current_point else locator
        strips.append({
            "strip_id": strip_id,
            "evidence_id": locator,
            "heading": heading,
            "text": " ".join(current_lines),
            "locator": strip_id,
            "metadata": metadata,
        })

    # If no points found and text is long, split by sentences
    if len(strips) <= 1 and len(text) > 350:
        sentences = [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if len(s.strip()) > 30]
        if len(sentences) > 1:
            strips = [
                {
                    "strip_id": f"{locator}_s{idx+1}",
                    "evidence_id": locator,
                    "heading": heading,
                    "text": sentence,
                    "locator": f"{locator}_s{idx+1}",
                    "metadata": metadata,
                }
                for idx, sentence in enumerate(sentences)
            ]

    # Fallback to whole text if not splittable
    if not strips:
        strips = [{
            "strip_id": locator,
            "evidence_id": locator,
            "heading": heading,
            "text": text,
            "locator": locator,
            "metadata": metadata,
        }]

    return strips

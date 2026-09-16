"""Legal Document Parser with Hierarchical Chunking (Legal-aware Chunking).

Breaks down Vietnamese normative legal documents following the hierarchical structure:
Văn bản -> Chương -> Điều -> Khoản -> Điểm.
Preserves provenance and deterministic locators for citation validation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


CHAPTER_PATTERN = re.compile(
    r"^(Chương\s+[IVXLCDM\d]+|Mục\s+[IVXLCDM\d]+|Phần\s+[IVXLCDM\d]+)[\.:\s]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
# Annex/appendix boundary — a "PHỤ LỤC" or "DANH MỤC" block appended after
# the main Điều body (e.g. a table of items "ban hành kèm theo" the document).
# Distinct from CHAPTER_PATTERN: it marks the *start of an annex region*, not
# a Chương/Mục nested inside the main body, and its numbered rows use bare
# "STT" (Số Thứ Tự) integers rather than "Điều"/"Khoản" numbering.
#
# Deliberately case-SENSITIVE (unlike the other patterns): these headings are
# always rendered in full caps in official Vietnamese legal PDFs, and the
# lowercase phrase "danh mục" (the common noun "list") appears constantly in
# ordinary prose throughout the preamble and Điều body — matching it
# case-insensitively misfires on those wrapped prose lines as a false annex
# boundary.
ANNEX_PATTERN = re.compile(
    r"^(PHỤ LỤC|DANH MỤC)\b[\.:\s]*(.*)$",
    re.MULTILINE,
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
# A bare-integer line inside an annex table's "STT" column (e.g. "10" on its
# own line, description following on subsequent lines) — distinct from
# CLAUSE_PATTERN, which requires the number and clause text on the same line
# ("1. Nội dung..."). Matched only against the *expected next* STT value
# (tracked in `parse_legal_document`) so page numbers and other stray bare
# digits interleaved by PDF text extraction are never mistaken for a new row.
STT_ITEM_PATTERN = re.compile(r"^(\d{1,3})$")


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
    current_article_is_stt_item = False
    in_annex = False
    next_stt = 1

    def flush_article():
        nonlocal current_article_lines, current_article_page_start, current_article_page_end
        nonlocal current_article, current_article_title, current_article_is_stt_item
        if not current_article or not current_article_lines:
            current_article_page_start = None
            current_article_page_end = None
            return

        article_text = "\n".join(current_article_lines).strip()
        page_start = current_article_page_start
        page_end = current_article_page_end

        if current_article_is_stt_item:
            # Annex/appendix table row ("STT N" inside a Mục) — the finest unit
            # this document defines for it; no further Khoản/Điểm decomposition
            # applies, unlike a real Điều's body.
            stt_match = re.search(r"\d+", current_article)
            stt_num = stt_match.group(0) if stt_match else current_article
            chapter_slug = re.sub(r"[^A-Za-z0-9]", "", current_chapter).upper() or "ANNEX"
            base_id = f"{doc_id}_{chapter_slug}_STT{stt_num}"
            prov_id = make_unique_id(base_id)
            heading = current_chapter_title or current_chapter
            breadcrumb = f"{doc_title} > {current_chapter} > STT {stt_num}"

            provisions.append({
                "id": prov_id,
                "document_id": doc_id,
                "document_number": doc_number,
                "chapter": current_chapter,
                "article": "",
                "clause": "",
                "point": f"STT {stt_num}",
                "heading": heading,
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
                    "article": "",
                    "clause": "",
                    "point": f"STT {stt_num}",
                    "locator": prov_id,
                }
            })

            current_article_lines = []
            current_article_page_start = None
            current_article_page_end = None
            current_article = ""
            current_article_title = ""
            current_article_is_stt_item = False
            return

        art_match = re.search(r"\d+", current_article)
        art_num = art_match.group(0) if art_match else current_article

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

        # Check Annex/Appendix heading ("Phụ lục", "Danh mục ...") — checked
        # before Chapter/Article so its own STT-numbered rows are recognized
        # rather than merged into the preceding Điều's last Khoản.
        annex_match = ANNEX_PATTERN.match(stripped)
        if annex_match:
            flush_article()
            current_chapter = annex_match.group(1).strip()
            current_chapter_title = annex_match.group(2).strip()
            current_article = ""
            current_article_title = ""
            in_annex = True
            next_stt = 1
            continue

        # Check Chapter / Part / Mục heading
        ch_match = CHAPTER_PATTERN.match(stripped)
        if ch_match:
            flush_article()
            current_chapter = ch_match.group(1).strip()
            current_chapter_title = ch_match.group(2).strip()
            current_article = ""
            current_article_title = ""
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

        if in_annex:
            # A bare integer matching the *next expected* STT value starts a
            # new numbered row; any other stray bare digit (page numbers,
            # etc., interleaved by PDF text extraction between table rows)
            # falls through as ordinary content instead of a false boundary.
            stt_match = STT_ITEM_PATTERN.match(stripped)
            if stt_match and int(stt_match.group(1)) == next_stt:
                flush_article()
                current_article = f"STT {next_stt}"
                current_article_is_stt_item = True
                current_article_page_start = page_num
                current_article_page_end = page_num
                next_stt += 1
                continue
            if not current_article:
                # Continuation of the Mục/annex title before its first row
                # (e.g. a two-line title wrapped by the PDF layout).
                current_chapter_title = f"{current_chapter_title} {stripped}".strip()
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

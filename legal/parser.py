"""Legal Document Parser with Hierarchical Chunking (Legal-aware Chunking).

Breaks down Vietnamese normative legal documents following the hierarchical structure:
Văn bản -> Chương -> Điều -> Khoản -> Điểm.
Preserves provenance and deterministic locators for citation validation.

Structure recognition is layered instead of hardcoding one document's phrasing
for its non-Điều sections (Phụ lục / Danh mục / Biểu mẫu / ... — the trailing
annex name varies per document even though the underlying drafting convention
does not):

1. Official vocabulary (law-mandated, not a per-document quirk): every
   Vietnamese normative document follows Nghị định 78/2025/NĐ-CP (and its
   predecessors) — Phần -> Chương -> Mục -> Tiểu mục -> Điều -> Khoản -> Điểm,
   with Phụ lục identifiers/titles always rendered in full uppercase.
   CHAPTER_PATTERN/ARTICLE_PATTERN/CLAUSE_PATTERN/POINT_PATTERN encode exactly
   this vocabulary and nothing document-specific.
2. Generic structural fallback for anything else: a document's own
   non-standard section heading (e.g. "DANH MỤC ...", "BẢNG GIÁ ...", "MẪU SỐ
   01" — whatever that document actually calls its trailing annex) is
   recognized the same way a reader skims a scanned legal PDF: a short,
   standalone line with no lowercase letters and no terminal sentence
   punctuation, appearing after the document's Điều body has already started.
   `_is_heading_like` implements that signal; no specific heading word is
   hardcoded anywhere in this module.
3. Recurring page furniture (running headers/footers, letterhead, signature
   blocks, table column headers repeated on every page) is stripped before
   structural parsing by frequency: any short line containing a letter that
   appears verbatim 2+ times across the document is furniture, since real
   prose is never byte-identical across pages. This keeps #2 from mistaking a
   repeated table header for a new section on every page break.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


CHAPTER_PATTERN = re.compile(
    r"^(Phần\s+[IVXLCDM\d]+|Chương\s+[IVXLCDM\d]+|Tiểu\s+mục\s+[IVXLCDM\d]+|Mục\s+[IVXLCDM\d]+)(?=[\.:\s]|$)[\.:\s]*(.*)$",
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
# A bare-integer line inside a flat numbered table/annex row (e.g. "10" alone
# on its own line, the row's description following on subsequent lines) —
# distinct from CLAUSE_PATTERN, which requires the number and its text on one
# line ("1. Nội dung..."). Matched only against the *expected next* value
# (tracked in `parse_legal_document`) so page numbers and other stray bare
# digits interleaved by PDF text extraction are never mistaken for a new row.
STT_ITEM_PATTERN = re.compile(r"^(\d{1,3})$")

_HEADING_MIN_LEN = 4
_HEADING_MAX_LEN = 100


def _is_heading_like(line: str) -> bool:
    """Keyword-free structural heading signal.

    A line "looks like" a section heading when it is short, stands alone (no
    trailing sentence punctuation), and contains no lowercase letters — the
    rendering convention Vietnamese legal drafting rules mandate for Phụ lục
    titles, and that in practice every other top-level heading a document
    defines (official or not) also follows. Ordinary prose fails this: it
    wraps across many lines and virtually always ends a sentence/paragraph in
    terminal punctuation, and Vietnamese diacritics make accidental
    all-uppercase prose exceedingly rare.
    """
    if not (_HEADING_MIN_LEN <= len(line) <= _HEADING_MAX_LEN):
        return False
    if line[-1] in ".,;":
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if len(letters) < _HEADING_MIN_LEN:
        return False
    return all(not ch.islower() for ch in letters)


def _strip_recurring_boilerplate(
    lines: List[str], line_pages: List[Optional[int]]
) -> Tuple[List[str], List[Optional[int]]]:
    """Drop running headers/footers/letterhead/signature-block furniture.

    Any stripped line containing a letter that recurs verbatim 2+ times
    across the document is page furniture, not content — real prose is never
    byte-identical across pages. Pure-digit lines (STT/page numbers) are left
    untouched regardless of frequency: `parse_legal_document` already
    disambiguates those from noise by sequence position (the *expected next*
    STT value), which frequency alone cannot do since a genuine row number
    can coincidentally match an unrelated page number elsewhere.
    """
    counts = Counter(
        s for s in (l.strip() for l in lines) if s and any(ch.isalpha() for ch in s)
    )
    kept_lines: List[str] = []
    kept_pages: List[Optional[int]] = []
    for line, page in zip(lines, line_pages):
        stripped = line.strip()
        if stripped and any(ch.isalpha() for ch in stripped) and counts[stripped] >= 2:
            continue
        kept_lines.append(line)
        kept_pages.append(page)
    return kept_lines, kept_pages

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

    lines, line_pages = _strip_recurring_boilerplate(lines, line_pages)

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
    # True once the first Điều has been seen — the generic (keyword-free)
    # annex/section fallback only ever applies after this, so a document's
    # own front matter (letterhead, "CỘNG HÒA XÃ HỘI...", document-type
    # marker, etc. — all short, standalone, all-caps lines too) is never
    # mistaken for a section boundary.
    seen_first_article = False
    # True while skipping the (possibly line-wrapped) "(Ban hành kèm theo...)"
    # style parenthetical cross-reference that commonly follows a bare
    # section heading — generic on the leading "(", not on its wording, so it
    # never gets glued onto a heading's title (see the title-fill step below).
    in_paren_gap = False
    # "Phần mở đầu" — the official opening section every normative document
    # has before its first Điều (quốc hiệu/tiêu ngữ, issuing body, document
    # number, and — the substantive part — its "Căn cứ ..." legal-basis
    # recitals). Captured as its own provision instead of being silently
    # dropped like everything else that isn't a Điều/Khoản/Điểm/annex row.
    preamble_lines: List[str] = []
    preamble_page_start: Optional[int] = None
    preamble_page_end: Optional[int] = None
    in_preamble = True

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
        chapter_display = f"{current_chapter} {current_chapter_title}".strip() if current_chapter_title else current_chapter
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
            breadcrumb = f"{doc_title} > {chapter_display} > STT {stt_num}"

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
                breadcrumb = f"{doc_title} > {chapter_display} > {current_article}"
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
            breadcrumb = f"{doc_title} > {chapter_display} > {current_article}"
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

        # Article heading — highest-confidence, most specific marker.
        art_match = ARTICLE_PATTERN.match(stripped)
        if art_match:
            flush_article()
            current_article = art_match.group(1).strip()
            current_article_title = art_match.group(2).strip()
            current_article_page_start = page_num
            current_article_page_end = page_num
            seen_first_article = True
            in_preamble = False
            in_paren_gap = False
            continue

        # Official Phần / Chương / Mục / Tiểu mục heading (law-mandated
        # vocabulary — see module docstring).
        ch_match = CHAPTER_PATTERN.match(stripped)
        if ch_match:
            flush_article()
            current_chapter = ch_match.group(1).strip()
            current_chapter_title = ch_match.group(2).strip()
            current_article = ""
            current_article_title = ""
            in_paren_gap = False
            in_preamble = False
            if current_chapter.lower().startswith(("chương", "phần")):
                # A real Chương/Phần boundary always outranks an annex table —
                # any table in progress has ended. Mục/Tiểu mục are left
                # alone since they commonly subdivide an annex's own rows
                # (e.g. "Mục I" / "Mục II" inside a "Danh mục ..." annex).
                in_annex = False
            continue

        if in_preamble:
            # Everything before the document's first Điều/Chương/Mục/Phần —
            # quốc hiệu/tiêu ngữ, issuing body, document number, and its
            # "Căn cứ ..." legal-basis recitals — captured as one provision
            # below instead of being silently dropped. A bare number this
            # early is always a running page number (no real "Phần mở đầu"
            # content is ever just digits on their own line), not content.
            if not STT_ITEM_PATTERN.match(stripped):
                preamble_lines.append(stripped)
                if page_num is not None:
                    if preamble_page_start is None:
                        preamble_page_start = page_num
                    preamble_page_end = page_num
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
                in_paren_gap = False
                continue

        if not current_article and current_chapter:
            # Between a chapter/annex boundary and its first real provision —
            # everything here is that heading's own (possibly multi-line,
            # possibly inline-continued) title, except a "(...)" cross
            # reference clause (e.g. "(Ban hành kèm theo ...)"), which is
            # dropped rather than absorbed since it names a decree/issuer, not
            # the section's subject.
            if stripped.startswith("(") or in_paren_gap:
                in_paren_gap = ")" not in stripped
                continue
            current_chapter_title = f"{current_chapter_title} {stripped}".strip()
            continue

        if seen_first_article and _is_heading_like(stripped):
            # A document-specific section/annex heading with no official
            # keyword (e.g. "DANH MỤC ...", "PHỤ LỤC II"). Only eligible once
            # the body has already produced at least one Điều, so a
            # document's own front matter (letterhead, motto, document-type
            # marker — also short, standalone, all-caps lines) is never
            # mistaken for one. Deliberately NOT gated on `not in_annex`:
            # a document with several sequential annexes ("PHỤ LỤC I", "PHỤ
            # LỤC II", "PHỤ LỤC III", ...) must re-trigger this on every one
            # of them — gating it would let the first annex (or a false
            # positive, e.g. a signature-block line the cleaner didn't
            # already strip) permanently swallow every heading after it for
            # the rest of the document.
            flush_article()
            current_chapter = stripped
            current_chapter_title = ""
            current_article = ""
            current_article_title = ""
            in_annex = True
            next_stt = 1
            in_paren_gap = False
            continue

        if current_article and not in_annex and STT_ITEM_PATTERN.match(stripped):
            # A bare digits-only line surviving inside an Điều/Khoản body is
            # running page-number furniture left over from a page break,
            # never real content — no legal clause is ever just an isolated
            # digits-only line. (Annex/table STT rows are a different case,
            # already handled above via `in_annex`.)
            continue

        if current_article:
            current_article_lines.append(stripped)
            if page_num is not None:
                if current_article_page_start is None:
                    current_article_page_start = page_num
                current_article_page_end = page_num

    # Flush last article
    flush_article()

    if preamble_lines:
        preamble_text = "\n".join(preamble_lines).strip()
        prov_id = make_unique_id(f"{doc_id}_PREAMBLE")
        provisions.insert(0, {
            "id": prov_id,
            "document_id": doc_id,
            "document_number": doc_number,
            "chapter": "",
            "article": "",
            "clause": "",
            "point": "",
            "heading": "Căn cứ ban hành",
            "text": preamble_text,
            "locator": prov_id,
            "provenance": f"{doc_title} > Căn cứ ban hành",
            "page_start": preamble_page_start,
            "page_end": preamble_page_end,
            "metadata": {
                "document_id": doc_id,
                "document_number": doc_number,
                "document_title": doc_title,
                "chapter": "",
                "article": "",
                "clause": "",
                "locator": prov_id,
            }
        })

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

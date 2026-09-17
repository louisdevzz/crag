"""Text Cleaning & Normalization — sits between Parse/OCR and the Legal
Structure Parser (`legal.parser.parse_legal_document`):
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from legal.parser import ARTICLE_PATTERN, CHAPTER_PATTERN, _is_heading_like

# Invisible characters PDF/DOCX extraction sometimes leaves behind: zero-width
# space/non-joiner/joiner/marks, BOM, soft hyphen. Removed outright (they
# carry no visual or structural meaning); NBSP is folded into a regular
# space instead so the whitespace-collapsing pass below absorbs it.
_INVISIBLE_CHARS = re.compile("[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]")
_NBSP = re.compile("\u00a0")

# A line made *entirely* of repeated separator/decoration characters — dot
# leaders, dash/underscore rules, bullet rows — optionally followed by ONE
# trailing punctuation mark. Never matches a line carrying any actual word
# text (letters/digits break the class), so `Điều 1.`, `1.`, `a)` are always
# safe. The trailing mark covers the blank-fill lines official form
# templates render for a field to hand-write in, e.g.
# "........................................ ;" (verified against a real
# annex form in `01/2017/TT-BQP`) — pure decoration otherwise, just
# terminated by the form's own field-separator punctuation instead of
# running to end of line.
_DECORATION_LINE = re.compile(r"^[.\-_=~·•●○∙*\s]{4,}[;:,.]?\s*$")

# A numbered/lettered clause marker ("1.", "a)") whose *entire* body is
# itself pure dot-leader filler — a blank field on an official form template
# waiting to be hand-written in (e.g. "1. .......................... ;"),
# verified against real annex forms in `01/2017/TT-BQP`). Carries zero
# retrieval value; dropped whole (marker included) rather than leaving a
# structurally-real but semantically-empty "Khoản 1" in the parsed output.
_BLANK_CLAUSE_LINE = re.compile(
    r"^(\d{1,3}\.|[a-zđA-ZĐ]\))\s*[.\-_=~·•●○∙*\s]{4,}[;:,.]?\s*$",
    re.IGNORECASE,
)

# Table-of-contents row: some heading text, a run of 4+ dot-leader
# characters, then a trailing page number — e.g.
# "Điều 7 ........................... 12". Dropped whole rather than having
# just its dots stripped (see module docstring for why).
_TOC_LINE = re.compile(r"^.{2,80}\.{4,}\s*\d{1,4}\s*$")

# The "MỤC LỤC" ("Table of Contents") section title itself — once its rows
# (`_TOC_LINE`, above) are gone this bare title carries no retrieval value
# either.
_TOC_TITLE_LINE = re.compile(r"^(MỤC\s+LỤC|TABLE\s+OF\s+CONTENTS)$", re.IGNORECASE)

# Standalone running page number in an unambiguous format only: "Trang 12",
# "Trang 12/45", "Page 12", "12/45". A bare "12" with no prefix/suffix is
# intentionally NOT matched here (see module docstring).
_PAGE_NUMBER_LINE = re.compile(
    r"^(Trang|Page)\s+\d{1,4}(\s*/\s*\d{1,4})?$|^\d{1,4}\s*/\s*\d{1,4}$",
    re.IGNORECASE,
)

# Footer URL / scan artifact line.
_URL_LINE = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)

# Start of the "Nơi nhận:" (distribution list) signature block that
# terminates most Vietnamese normative documents.
_SIGNATURE_START = re.compile(r"^N[ơo]i\s+nh[ậa]n\s*:?\s*$", re.IGNORECASE)

# "(Đã ký)" / "(Đã ký, đóng dấu)" — the signature-stamp marker Vietnamese
# normative documents render in place of an actual signature. Unlike
# `_SIGNATURE_START`, this fires the signature-block skip even when there is
# no preceding "Nơi nhận:" distribution list (a real document, verified
# against `01/2017/TT-BQP`: its signature block is bare "KT. BỘ TRƯỞNG /
# THỨ TRƯỞNG / (Đã ký) / <tên>" with no "Nơi nhận:" anywhere near it) — see
# `clean_pages` for how the preceding title line gets retroactively popped.
_SIGNATURE_MARKER = re.compile(r"^\(\s*[ĐđDd][ãa]\s*k[ýy][^)]*\)$", re.IGNORECASE)


def _strip_invisible(line: str) -> str:
    line = unicodedata.normalize("NFC", line)
    line = _INVISIBLE_CHARS.sub("", line)
    line = _NBSP.sub(" ", line)
    return line


def _collapse_whitespace(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line).strip()


def clean_line(line: str) -> Optional[str]:
    """Clean one physical line.

    Returns the cleaned, whitespace-collapsed line; `""` for a genuinely
    blank line (kept as a paragraph separator upstream); `None` when the
    whole line is decoration/furniture and must be dropped.
    """
    line = _strip_invisible(line)
    stripped = _collapse_whitespace(line)
    if not stripped:
        return ""
    if _DECORATION_LINE.match(stripped):
        return None
    if _BLANK_CLAUSE_LINE.match(stripped):
        return None
    if _TOC_LINE.match(stripped):
        return None
    if _TOC_TITLE_LINE.match(stripped):
        return None
    if _PAGE_NUMBER_LINE.match(stripped):
        return None
    if _URL_LINE.match(stripped):
        return None
    return stripped


def clean_pages(pages_data: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Clean every page's text in place (returns new records; input untouched).

    Mirrors `UniversalLegalPreprocessor.extract_text_from_pdf`'s return shape
    `(full_text, page_records)` so it drops straight into
    `ingestion.pipeline.run_ingestion_pipeline` between text extraction and
    `legal.parser.parse_legal_document`, and `page_start`/`page_end`
    provenance keeps working unchanged.
    """
    cleaned_pages: List[Dict[str, Any]] = []
    full_text_chunks: List[str] = []
    in_signature = False
    sig_saw_title = False
    prev_blank = True  # suppress a leading blank line at the very start

    for page in pages_data:
        raw_lines = page.get("text", "").split("\n")
        kept: List[str] = []
        for raw_line in raw_lines:
            cleaned = clean_line(raw_line)
            if cleaned is None:
                continue

            if not cleaned:
                if not prev_blank and kept:
                    kept.append("")
                prev_blank = True
                continue
            prev_blank = False

            if not in_signature and _SIGNATURE_MARKER.match(cleaned):
                # "(Đã ký)" itself never precedes "Nơi nhận:" — it IS the
                # signature block, retroactively: pop the title line(s) that
                # led up to it ("KT. .../THỨ TRƯỞNG", possibly a blank line
                # between them) straight back out of `kept`, bounded to the
                # last 3 lines so an unrelated distant heading is never eaten.
                for _ in range(3):
                    if kept and (kept[-1] == "" or _is_heading_like(kept[-1])):
                        kept.pop()
                    else:
                        break
                prev_blank = bool(kept) and kept[-1] == ""
                in_signature = True
                sig_saw_title = True  # the signer's name follows next -> drop it too
                continue

            if not in_signature and _SIGNATURE_START.match(cleaned):
                in_signature = True
                sig_saw_title = False
                continue

            if in_signature:
                if ARTICLE_PATTERN.match(cleaned) or CHAPTER_PATTERN.match(cleaned):
                    in_signature = False
                    sig_saw_title = False
                    # fall through: this line is real structure, keep it.
                elif cleaned.startswith("-"):
                    # Distribution-list bullet under "Nơi nhận:".
                    continue
                elif _is_heading_like(cleaned):
                    # "KT. .../THỨ TRƯỞNG"-style title line — the signer's
                    # name (usually mixed-case, so not heading-like itself)
                    # follows immediately after.
                    sig_saw_title = True
                    continue
                elif sig_saw_title:
                    # The one signer-name line right after the title —
                    # drop it and the block is over.
                    in_signature = False
                    sig_saw_title = False
                    continue
                else:
                    in_signature = False
                    sig_saw_title = False
                    # fall through: no title was ever seen, not a real
                    # signature block after all — keep this line.

            kept.append(cleaned)

        page_text = "\n".join(kept).strip("\n")
        cleaned_pages.append({**page, "text": page_text})
        if page_text:
            full_text_chunks.append(page_text)

    cleaned_text = "\n\n".join(full_text_chunks)
    return cleaned_text, cleaned_pages

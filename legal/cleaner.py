"""Text cleaning and normalization module for legal document ingestion."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from legal.parser import ARTICLE_PATTERN, CHAPTER_PATTERN, _is_heading_like

# Invisible characters and non-breaking spaces.
_INVISIBLE_CHARS = re.compile("[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]")
_NBSP = re.compile("\u00a0")

# Repeated separator and decoration line pattern.
_DECORATION_LINE = re.compile(r"^[.\-_=~·•●○∙*\s]{4,}[;:,.]?\s*$")

# Blank clause marker line on form templates.
_BLANK_CLAUSE_LINE = re.compile(
    r"^(\d{1,3}\.|[a-zđA-ZĐ]\))\s*[.\-_=~·•●○∙*\s]{4,}[;:,.]?\s*$",
    re.IGNORECASE,
)

# Table-of-contents entry line pattern.
_TOC_LINE = re.compile(r"^.{2,80}\.{4,}\s*\d{1,4}\s*$")

# Table-of-contents section title line pattern.
_TOC_TITLE_LINE = re.compile(r"^(MỤC\s+LỤC|TABLE\s+OF\s+CONTENTS)$", re.IGNORECASE)

# Unambiguous standalone page number pattern.
_PAGE_NUMBER_LINE = re.compile(
    r"^(Trang|Page)\s+\d{1,4}(\s*/\s*\d{1,4})?$|^\d{1,4}\s*/\s*\d{1,4}$",
    re.IGNORECASE,
)

# Footer URL / scan artifact line.
_URL_LINE = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)

# Start of distribution list ("Nơi nhận:").
_SIGNATURE_START = re.compile(r"^N[ơo]i\s+nh[ậa]n\s*:?\s*$", re.IGNORECASE)

# Signature marker pattern ("(Đã ký)").
_SIGNATURE_MARKER = re.compile(r"^\(\s*[ĐđDd][ãa]\s*k[ýy][^)]*\)$", re.IGNORECASE)


def _strip_invisible(line: str) -> str:
    line = unicodedata.normalize("NFC", line)
    line = _INVISIBLE_CHARS.sub("", line)
    line = _NBSP.sub(" ", line)
    return line


def _collapse_whitespace(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line).strip()


def clean_line(line: str) -> Optional[str]:
    """Clean one physical line, returning cleaned text, blank line, or None if dropped."""
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
    """Clean text across extracted pages, stripping furniture and normalizing spacing."""
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

"""Universal Legal Data Pre-processing Pipeline for Vietnamese Normative Documents.

Capabilities:
1. Universal Format Ingestion: Handles digital text PDFs, scanned/image PDFs, DOCX, and TXT.
2. Multimodal Vision LLM OCR: When pages are scanned images without text layers,
   renders the page and transcribes via Vision LLM (OpenAI, Groq, OpenRouter, Ollama) with disk caching.
3. Automatic Legal Metadata Extraction: Extracts document number, title, type, authority,
   promulgation date, and effective date.
4. Hierarchical Structure Parsing: Breaks text into Chương -> Điều -> Khoản -> Điểm
   with deterministic locators and provenance breadcrumbs.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

from config import DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from legal.parser import parse_legal_document, split_into_legal_strips
from legal.temporal import parse_date


OCR_CACHE_DIR = PROCESSED_DATA_DIR / "ocr_cache"
SCANNED_PAGES_DIR = PROCESSED_DATA_DIR / "scanned_pages"


def _build_openai_vision(model: str, api_key: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, temperature=0.0)


def _build_groq_vision(model: str, api_key: str):
    from langchain_groq import ChatGroq
    return ChatGroq(model=model, api_key=api_key, temperature=0.0)


def _build_openrouter_vision(model: str, api_key: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, base_url="https://openrouter.ai/api/v1", temperature=0.0)


# Per-provider wiring for `_call_vision_llm`: env var holding the key, the
# placeholder prefix `.env.example` ships (skipped so a fresh, un-configured
# clone never burns a request on it), the default model when the caller
# didn't set VISION_MODEL, and the LangChain client builder. "qwen/qwen3.8-27b"
# is Groq's current natively-multimodal chat model and the one this project
# already uses for text generation (LLM_MODEL) — verified working for image
# transcription directly against the Groq API; the previous default,
# "llama-3.2-11b-vision-preview", was decommissioned by Groq in April 2025.
_VISION_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "env_key": "GROQ_API_KEY",
        "placeholder_prefix": "gsk_your_",
        "default_model": "qwen/qwen3.8-27b",
        "build": _build_groq_vision,
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "placeholder_prefix": "sk-your_",
        "default_model": "gpt-4o-mini",
        "build": _build_openai_vision,
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "placeholder_prefix": "sk-or-your_",
        "default_model": "google/gemini-flash-1.5",
        "build": _build_openrouter_vision,
    },
}

class UniversalLegalPreprocessor:
    """End-to-end pre-processing pipeline for any Vietnamese legal document."""

    def __init__(
        self,
        vision_provider: Optional[str] = None,
        vision_model: Optional[str] = None,
        enable_vision_ocr: bool = True,
    ):
        self.vision_provider = (vision_provider or os.getenv("VISION_PROVIDER") or os.getenv("LLM_PROVIDER", "groq")).lower().strip()
        self.vision_model = (
            vision_model
            or os.getenv("VISION_MODEL")
            or _VISION_PROVIDERS.get(self.vision_provider, {}).get("default_model", "gpt-4o-mini")
        )
        self.enable_vision_ocr = enable_vision_ocr
        OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        SCANNED_PAGES_DIR.mkdir(parents=True, exist_ok=True)

    def extract_text_from_pdf(
        self,
        pdf_path: str | Path,
        max_pages: Optional[int] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text from PDF page by page. Uses digital text if present; falls back to Vision OCR.

        Returns
        -------
        (full_text, page_records)
        """
        pdf_path = Path(pdf_path)
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        limit = min(total_pages, max_pages) if max_pages else total_pages

        pages_data: List[Dict[str, Any]] = []
        full_text_chunks: List[str] = []

        print(f"[{pdf_path.name}] Processing {limit}/{total_pages} pages...")

        for pno in range(limit):
            page = doc[pno]
            raw_text = page.get_text("text").strip()

            # Check if page has digital text
            if len(raw_text) > 50:
                pages_data.append({
                    "page_number": pno + 1,
                    "text": raw_text,
                    "source_type": "digital_text",
                })
                full_text_chunks.append(raw_text)
            else:
                # Page is scanned image or empty
                print(f"  Page {pno + 1}: No text layer found. Rendering page image...")
                page_text = self._handle_scanned_page(page, pno + 1, pdf_path.stem)
                pages_data.append({
                    "page_number": pno + 1,
                    "text": page_text,
                    "source_type": "vision_ocr" if page_text else "empty_image",
                })
                if page_text:
                    full_text_chunks.append(page_text)

        combined_text = "\n\n".join(full_text_chunks)
        return combined_text, pages_data

    def _handle_scanned_page(self, page: pymupdf.Page, page_num: int, doc_stem: str) -> str:
        """Handle scanned page: check cache, render image, call Vision LLM or save for transcription."""
        cache_key = f"{doc_stem}_p{page_num}.txt"
        cache_file = OCR_CACHE_DIR / cache_key

        if cache_file.exists():
            print(f"  Page {page_num}: Loaded from OCR cache.")
            return cache_file.read_text(encoding="utf-8")

        # Render page to PNG image
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        # Save rendered image
        doc_scanned_dir = SCANNED_PAGES_DIR / doc_stem
        doc_scanned_dir.mkdir(parents=True, exist_ok=True)
        img_path = doc_scanned_dir / f"page_{page_num:03d}.png"
        img_path.write_bytes(img_bytes)

        if not self.enable_vision_ocr:
            return ""

        # Attempt Vision LLM transcription
        transcribed = self._call_vision_llm(img_bytes, page_num, doc_stem)
        if transcribed:
            cache_file.write_text(transcribed, encoding="utf-8")
            return transcribed

        return ""

    def _call_vision_llm(self, image_bytes: bytes, page_num: int, doc_stem: str) -> Optional[str]:
        """Call Vision LLM to transcribe legal page image into exact Vietnamese text.

        Tries `self.vision_provider`/`self.vision_model` (VISION_PROVIDER/VISION_MODEL,
        defaulting to LLM_PROVIDER) first, then falls back to the other configured
        providers in `_VISION_PROVIDERS` — each skipped outright when its API key is
        absent or still the placeholder shipped in `.env.example`, so a single-provider
        setup (the common case) never wastes a request on an unconfigured one.
        """
        from langchain_core.messages import HumanMessage

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_image}"

        prompt = (
            "Bạn là chuyên gia số hóa văn bản quy phạm pháp luật Việt Nam. "
            "Hãy đọc hình ảnh trang văn bản này và chuyển đổi chính xác từng từ thành văn bản (text), "
            "giữ nguyên toàn bộ số hiệu, tên Chương, Điều, Khoản, Điểm, bảng biểu và dấu câu. "
            "Tuyệt đối không tóm tắt, không thêm lời bình, chỉ trả về nội dung văn bản nguyên gốc."
        )
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])

        provider_order = [self.vision_provider] + [
            p for p in _VISION_PROVIDERS if p != self.vision_provider
        ]
        for provider in provider_order:
            spec = _VISION_PROVIDERS.get(provider)
            if spec is None:
                continue
            api_key = os.getenv(spec["env_key"], "")
            if not api_key or api_key.startswith(spec["placeholder_prefix"]):
                continue
            model = self.vision_model if provider == self.vision_provider else spec["default_model"]
            try:
                llm = spec["build"](model, api_key)
                res = llm.invoke([msg])
                print(f"  Page {page_num}: Successfully transcribed via {provider} Vision LLM ({model}).")
                return res.content.strip()
            except Exception as e:
                print(f"  Page {page_num}: {provider} Vision failed ({e})")

        return None

    def extract_metadata(self, text: str, file_path: Path) -> Dict[str, Any]:
        """Automatically detect legal document metadata from text and filename."""
        doc_id = re.sub(r"[^A-Za-z0-9_]", "_", file_path.stem).upper()

        # 1. Document Number
        doc_num_pattern = re.compile(
            r"(?:Luật số|Bộ luật số|Nghị định số|Quyết định số|Thông tư số|Số)[:\s]*([0-9]+/[0-9]+/[A-ZĐa-zđ0-9\-_]+)",
            re.IGNORECASE,
        )
        doc_num_m = doc_num_pattern.search(text[:4000])
        doc_number = doc_num_m.group(1).strip() if doc_num_m else ""

        # Fallback from filename (e.g. 41-2024-qh15 -> 41/2024/QH15)
        if not doc_number:
            fn_m = re.search(r"(\d+)[\-_](\d{4})[\-_]([a-zđ0-9]+)", file_path.stem, re.IGNORECASE)
            if fn_m:
                doc_number = f"{fn_m.group(1)}/{fn_m.group(2)}/{fn_m.group(3).upper()}"

        # 2. Document Type
        doc_type = "Văn bản quy phạm pháp luật"
        for t in ["BỘ LUẬT", "LUẬT", "NGHỊ ĐỊNH", "THÔNG TƯ", "QUYẾT ĐỊNH", "NGHỊ QUYẾT"]:
            if t in text[:2000].upper():
                doc_type = t.title()
                break

        # 3. Document Title
        title = ""
        # Look for LUẬT / BỘ LUẬT / NGHỊ ĐỊNH line
        lines = [l.strip() for l in text[:3000].split("\n") if l.strip()]
        for i, l in enumerate(lines[:30]):
            upper = l.upper()
            if upper in ("LUẬT", "BỘ LUẬT"):
                # Title is usually next line
                if i + 1 < len(lines):
                    title = f"{upper.title()} {lines[i+1]}"
                break
            elif upper.startswith("NGHỊ ĐỊNH") or upper.startswith("QUYẾT ĐỊNH") or upper.startswith("THÔNG TƯ"):
                title = l
                break

        if not title:
            # Fallback to file parent folder and stem
            title = f"{doc_type} {file_path.stem}"

        # 4. Issuing Authority
        authority = "Quốc hội"
        if "CHÍNH PHỦ" in text[:2000].upper():
            authority = "Chính phủ"
        elif "THỦ TƯỚNG" in text[:2000].upper():
            authority = "Thủ tướng Chính phủ"
        elif "QUỐC HỘI" in text[:2000].upper():
            authority = "Quốc hội"

        # 5. Promulgation & Effective Dates
        issued_at = None
        effective_from = None
        status = "effective"

        # Look for "tháng ... năm ..." or "ngày ... tháng ... năm ..."
        date_pattern = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
        dates = date_pattern.findall(text[:4000])
        if dates:
            d, m, y = dates[0]
            issued_at = f"{y}-{int(m):02d}-{int(d):02d}"

        # Effective date often at the end: "Luật này có hiệu lực thi hành từ ngày..."
        eff_pattern = re.compile(
            r"(?:có hiệu lực|hiệu lực thi hành)(?:\s+kể)?\s+từ\s+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            re.IGNORECASE,
        )
        eff_m = eff_pattern.search(text[-6000:] if len(text) > 6000 else text)
        if eff_m:
            d, m, y = eff_m.groups()
            effective_from = f"{y}-{int(m):02d}-{int(d):02d}"

        # Fallback doc_id derived from doc_number if available
        if doc_number:
            clean_num = re.sub(r"[^A-Za-z0-9]", "_", doc_number).upper()
            doc_id = f"DOC_{clean_num}"

        return {
            "id": doc_id,
            "document_number": doc_number or file_path.stem,
            "title": title,
            "document_type": doc_type,
            "issuing_authority": authority,
            "issued_at": issued_at,
            "effective_from": effective_from or issued_at,
            "effective_to": None,
            "status": status,
            "source_url": f"file://{file_path.resolve()}",
            "file_path": str(file_path.resolve()),
        }

    def process_file(
        self,
        file_path: str | Path,
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """End-to-end processing of a single legal file into structured provisions.

        Returns
        -------
        dict with keys: metadata, raw_text, provisions, strips, stats
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            raw_text, pages_data = self.extract_text_from_pdf(file_path, max_pages=max_pages)
        elif ext in (".docx", ".doc"):
            raw_text = self._extract_text_from_docx(file_path)
            pages_data = [{"page_number": 1, "text": raw_text, "source_type": "docx"}]
        elif ext in (".txt", ".md", ".html"):
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
            pages_data = [{"page_number": 1, "text": raw_text, "source_type": "text"}]
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        metadata = self.extract_metadata(raw_text, file_path)
        provisions = parse_legal_document(raw_text, metadata, pages_data=pages_data)

        # Knowledge refinement legal strips
        all_strips = []
        for prov in provisions:
            all_strips.extend(split_into_legal_strips(prov))

        result = {
            "metadata": metadata,
            "raw_text_length": len(raw_text),
            "pages_count": len(pages_data),
            "provisions_count": len(provisions),
            "strips_count": len(all_strips),
            "provisions": provisions,
            "strips": all_strips,
        }

        # Save structured JSON to data/processed/
        out_json = PROCESSED_DATA_DIR / f"{metadata['id']}.json"
        out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved processed document: {out_json} ({len(provisions)} provisions, {len(all_strips)} strips)")

        return result

    def _extract_text_from_docx(self, docx_path: Path) -> str:
        """Extract text from a Word document — modern `.docx` (OOXML/zip) or
        legacy binary `.doc` (OLE2 Compound File — an entirely different
        container format, not a zip, so python-docx cannot open it at all;
        it raises `zipfile.BadZipFile` on one).

        `.docx` is parsed directly with python-docx. Legacy `.doc` is parsed
        with `sharepoint2text`, a pure-Python OLE2/MS-DOC reader — no
        external binary (antiword/LibreOffice) or JVM (Apache Tika)
        dependency, unlike every other common approach to this format.
        """
        if docx_path.suffix.lower() == ".doc":
            import sharepoint2text
            document = next(sharepoint2text.read_file(docx_path))
            return document.full_text
        import docx
        doc = docx.Document(docx_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    def process_all(self, target_dir: str | Path = DATA_DIR) -> List[Dict[str, Any]]:
        """Scan and process all legal documents in the directory."""
        target_dir = Path(target_dir)
        results = []
        # Find all PDFs excluding cached and temp files
        all_pdfs = [
            p for p in target_dir.rglob("*.pdf")
            if "processed" not in str(p) and "ocr_cache" not in str(p) and not p.name.startswith(".")
        ]

        print(f"Found {len(all_pdfs)} PDF files to process in {target_dir}")
        for pdf_path in sorted(all_pdfs):
            try:
                res = self.process_file(pdf_path)
                results.append(res)
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")

        # Write combined manifest
        manifest = {
            "total_documents": len(results),
            "total_provisions": sum(r["provisions_count"] for r in results),
            "total_strips": sum(r["strips_count"] for r in results),
            "documents": [r["metadata"] for r in results],
        }
        manifest_path = DATA_DIR / "corpus_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nCompleted preprocessing! Corpus manifest written to {manifest_path}")
        return results


if __name__ == "__main__":
    preprocessor = UniversalLegalPreprocessor()
    preprocessor.process_all()

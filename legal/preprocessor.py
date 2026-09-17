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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pymupdf

from config import DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from legal.parser import parse_legal_document, split_into_legal_strips
from legal.temporal import parse_date
from logging_config import get_logger

log = get_logger(__name__)

OCR_CACHE_DIR = PROCESSED_DATA_DIR / "ocr_cache"
SCANNED_PAGES_DIR = PROCESSED_DATA_DIR / "scanned_pages"

# How many pages' Vision LLM OCR calls run concurrently. Rendering a page to
# an image (`pymupdf`) is CPU-only and effectively instant; transcribing it
# is a several-second network round trip and the actual bottleneck for a
# large scanned document, so only that step is parallelized (bounded to
# avoid tripping the vision provider's rate limit).
OCR_CONCURRENCY = max(1, int(os.getenv("OCR_CONCURRENCY", "4")))



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
        on_ocr_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text from PDF page by page. Uses digital text if present; falls back to Vision OCR.

        Rendering (`pymupdf`, CPU-only, milliseconds/page) always runs
        sequentially on this thread — `fitz` Document/Page objects aren't
        safe to touch from multiple threads. The real bottleneck for a large
        scanned document is each page's Vision LLM network round trip
        (seconds); only that step runs concurrently, across up to
        `OCR_CONCURRENCY` worker threads once every page's image bytes have
        already been rendered — a 45-page scan OCRs in roughly
        `45 / OCR_CONCURRENCY` round trips instead of 45.

        `on_ocr_progress(completed, total)` — when given — fires after each
        OCR'd page so the caller (`ingestion.pipeline`) can surface live
        "OCR trang N/M" progress instead of the stage sitting still for
        however long the whole document takes.

        Returns
        -------
        (full_text, page_records)
        """
        pdf_path = Path(pdf_path)
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        limit = min(total_pages, max_pages) if max_pages else total_pages

        pages_data: List[Optional[Dict[str, Any]]] = [None] * limit
        pending: List[Tuple[int, bytes]] = []  # (0-based page index, rendered PNG bytes) awaiting OCR

        log.info("[%s] processing %d/%d pages", pdf_path.name, limit, total_pages)

        for pno in range(limit):
            page = doc[pno]
            raw_text = page.get_text("text").strip()

            if len(raw_text) > 50:
                pages_data[pno] = {"page_number": pno + 1, "text": raw_text, "source_type": "digital_text"}
                continue

            cached = self._read_ocr_cache(pdf_path.stem, pno + 1)
            if cached is not None:
                log.info("[%s] page %d/%d: loaded from OCR cache", pdf_path.name, pno + 1, limit)
                pages_data[pno] = {
                    "page_number": pno + 1, "text": cached,
                    "source_type": "vision_ocr" if cached else "empty_image",
                }
                continue

            log.info("[%s] page %d/%d: no text layer -> rendering for OCR", pdf_path.name, pno + 1, limit)
            pending.append((pno, self._render_page_image(page, pno + 1, pdf_path.stem)))

        doc.close()  # page image bytes already extracted; the OCR calls below never touch `doc`/`page` again

        total_pending = len(pending)
        if pending and self.enable_vision_ocr:
            completed = 0
            max_workers = min(OCR_CONCURRENCY, total_pending)
            log.info(
                "[%s] %d page(s) need Vision OCR -> dispatching across %d worker thread(s)",
                pdf_path.name, total_pending, max_workers,
            )
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="vision-ocr") as ex:
                futures = {
                    ex.submit(self._transcribe_and_cache, img_bytes, pno + 1, pdf_path.stem): pno
                    for pno, img_bytes in pending
                }
                for fut in as_completed(futures):
                    pno = futures[fut]
                    try:
                        text = fut.result()
                    except Exception as e:
                        log.error("[%s] page %d/%d: OCR raised %s -> treated as empty page", pdf_path.name, pno + 1, limit, e)
                        text = ""
                    pages_data[pno] = {
                        "page_number": pno + 1, "text": text,
                        "source_type": "vision_ocr" if text else "empty_image",
                    }
                    completed += 1
                    log.info("[%s] OCR progress: %d/%d page(s) done", pdf_path.name, completed, total_pending)
                    if on_ocr_progress:
                        on_ocr_progress(completed, total_pending)
        elif pending:
            # Vision OCR explicitly disabled for this call -> leave scanned pages empty rather than block.
            for pno, _ in pending:
                pages_data[pno] = {"page_number": pno + 1, "text": "", "source_type": "empty_image"}

        full_text_chunks = [p["text"] for p in pages_data if p and p.get("text")]
        combined_text = "\n\n".join(full_text_chunks)
        return combined_text, pages_data

    def _read_ocr_cache(self, doc_stem: str, page_num: int) -> Optional[str]:
        cache_file = OCR_CACHE_DIR / f"{doc_stem}_p{page_num}.txt"
        return cache_file.read_text(encoding="utf-8") if cache_file.exists() else None

    def _render_page_image(self, page: pymupdf.Page, page_num: int, doc_stem: str) -> bytes:
        """Render one page to PNG bytes and save it to disk (`pymupdf`, CPU-only, always
        called on the main thread — never inside the OCR worker pool)."""
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        doc_scanned_dir = SCANNED_PAGES_DIR / doc_stem
        doc_scanned_dir.mkdir(parents=True, exist_ok=True)
        (doc_scanned_dir / f"page_{page_num:03d}.png").write_bytes(img_bytes)
        return img_bytes

    def _transcribe_and_cache(self, image_bytes: bytes, page_num: int, doc_stem: str) -> str:
        """Runs on an OCR worker thread: one page's Vision LLM round trip, timed, plus its
        disk-cache write on success."""
        start = time.perf_counter()
        transcribed = self._call_vision_llm(image_bytes, page_num, doc_stem)
        elapsed = time.perf_counter() - start
        if transcribed:
            (OCR_CACHE_DIR / f"{doc_stem}_p{page_num}.txt").write_text(transcribed, encoding="utf-8")
            log.info("[%s] page %d: OCR done in %.2fs (%d chars)", doc_stem, page_num, elapsed, len(transcribed))
            return transcribed
        log.warning("[%s] page %d: OCR produced no text after %.2fs", doc_stem, page_num, elapsed)
        return ""

    def _call_vision_llm(self, image_bytes: bytes, page_num: int, doc_stem: str) -> Optional[str]:
        """Call Vision LLM to transcribe legal page image into exact Vietnamese text.

        Tries `self.vision_provider`/`self.vision_model` (VISION_PROVIDER/VISION_MODEL,
        defaulting to LLM_PROVIDER) first, then falls back to the other configured
        providers in `_VISION_PROVIDERS` — each skipped outright when its API key is
        absent or still the placeholder shipped in `.env.example`, so a single-provider
        setup (the common case) never wastes a request on an unconfigured one.

        Runs on an OCR worker thread (see `extract_text_from_pdf`) — safe: each call
        builds its own client instance (`spec["build"](...)`) rather than sharing one.
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
                log.info("[%s] page %d: transcribed via %s Vision LLM (%s)", doc_stem, page_num, provider, model)
                return res.content.strip()
            except Exception as e:
                log.warning("[%s] page %d: %s Vision failed (%s)", doc_stem, page_num, provider, e)

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
        log.info("Saved processed document: %s (%d provisions, %d strips)", out_json, len(provisions), len(all_strips))

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

        log.info("Found %d PDF files to process in %s", len(all_pdfs), target_dir)
        for pdf_path in sorted(all_pdfs):
            try:
                res = self.process_file(pdf_path)
                results.append(res)
            except Exception as e:
                log.error("Error processing %s: %s", pdf_path, e)

        # Write combined manifest
        manifest = {
            "total_documents": len(results),
            "total_provisions": sum(r["provisions_count"] for r in results),
            "total_strips": sum(r["strips_count"] for r in results),
            "documents": [r["metadata"] for r in results],
        }
        manifest_path = DATA_DIR / "corpus_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Completed preprocessing! Corpus manifest written to %s", manifest_path)
        return results


if __name__ == "__main__":
    preprocessor = UniversalLegalPreprocessor()
    preprocessor.process_all()

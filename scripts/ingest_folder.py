"""CLI script to ingest a folder of legal documents into the Knowledge Base."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import UPLOAD_DIR
from ingestion import documents as documents_repo
from ingestion import indexer
from ingestion import jobs as jobs_repo
from ingestion.pipeline import run_ingestion_pipeline
from logging_config import get_logger

log = get_logger("ingest_folder")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


def find_supported_files(folder_path: Path, recursive: bool = True) -> List[Path]:
    """Find all supported legal documents in the given folder."""
    files: List[Path] = []
    pattern = "**/*" if recursive else "*"
    for p in folder_path.glob(pattern):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS and not p.name.startswith("."):
            files.append(p)
    return sorted(files)


def _prepare_document(file_path: Path, replace: bool) -> Dict[str, Any]:
    """Validate, hash, and persist a single file record into the database."""
    filename = file_path.name
    ext = file_path.suffix.lower()

    try:
        content = file_path.read_bytes()
    except Exception as exc:
        return {"filename": filename, "status": "ERROR", "error": f"Không đọc được tệp: {exc}"}

    if not content:
        return {"filename": filename, "status": "ERROR", "error": "Tệp rỗng"}

    content_hash = hashlib.sha256(content).hexdigest()
    existing = documents_repo.find_by_content_hash(content_hash)

    if existing and existing["status"] != "FAILED" and not replace:
        return {
            "filename": filename,
            "status": "SKIPPED",
            "document_id": existing["id"],
            "message": f"Đã tồn tại trong hệ thống (status={existing['status']}). Dùng --replace để nạp lại.",
        }

    if existing:
        indexer.remove_document_from_chroma(existing["id"])
        documents_repo.delete_document(existing["id"])

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = documents_repo.new_document_id()
    dest_path = UPLOAD_DIR / f"{doc_id}{ext}"
    dest_path.write_bytes(content)

    doc = documents_repo.create_document(
        filename=filename,
        file_path=str(dest_path),
        file_type=ext,
        content_hash=content_hash,
        document_id=doc_id,
    )
    job = jobs_repo.create_job(doc["id"])
    return {"filename": filename, "status": "ACCEPTED", "document_id": doc["id"], "job_id": job["id"]}


def ingest_folder(
    folder_path: str | Path,
    replace: bool = False,
    recursive: bool = True,
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Scan and ingest all legal documents from a folder into SQLite, Chroma, and BM25."""
    start_time = time.perf_counter()
    folder = Path(folder_path).resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"❌ Thư mục không tồn tại: {folder}", file=sys.stderr)
        return {"success": False, "error": f"Folder not found: {folder}"}

    print(f"📂 [INGEST] Quét thư mục: {folder} (recursive={recursive})")
    candidate_files = find_supported_files(folder, recursive=recursive)

    if not candidate_files:
        print(f"⚠️  Không tìm thấy tệp hợp lệ nào trong {folder}. Định dạng hỗ trợ: {sorted(ALLOWED_EXTENSIONS)}")
        return {"success": True, "total": 0, "accepted": 0, "skipped": 0, "failed": 0}

    print(f"🔍 Tìm thấy {len(candidate_files)} tệp văn bản hợp lệ.")

    accepted_docs: List[Dict[str, Any]] = []
    skipped_count = 0
    error_results: List[Dict[str, Any]] = []

    for file_path in candidate_files:
        prep = _prepare_document(file_path, replace=replace)
        if prep["status"] == "ACCEPTED":
            accepted_docs.append(prep)
            print(f"   [+] Chấp nhận: {prep['filename']} (id={prep['document_id']})")
        elif prep["status"] == "SKIPPED":
            skipped_count += 1
            print(f"   [-] Bỏ qua (đã có): {prep['filename']}")
        else:
            error_results.append(prep)
            print(f"   [!] Lỗi chuẩn bị: {prep['filename']} — {prep.get('error')}")

    if not accepted_docs:
        print(f"\n✅ Hoàn tất kiểm tra: 0 tệp mới cần nạp ({skipped_count} tệp đã tồn tại).")
        return {"success": True, "total": len(candidate_files), "accepted": 0, "skipped": skipped_count, "failed": len(error_results)}

    workers = max_workers or max(1, int(os.getenv("INGESTION_WORKERS", "3")))
    print(f"\n🚀 Bắt đầu xử lý {len(accepted_docs)} tài liệu với {workers} luồng xử lý...")

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ingest-cli") as executor:
        future_to_doc = {
            executor.submit(run_ingestion_pipeline, doc["document_id"], False): doc
            for doc in accepted_docs
        }

        for future in as_completed(future_to_doc):
            doc = future_to_doc[future]
            doc_name = doc["filename"]
            try:
                future.result()
                doc_record = documents_repo.get_document(doc["document_id"])
                chunks_count = doc_record.get("chunk_count", 0) if doc_record else 0
                success_count += 1
                print(f"   ✅ [READY] {doc_name} — {chunks_count} chunks đã phân tách & nhúng vector")
            except Exception as exc:
                fail_count += 1
                log.error("Pipeline thất bại cho %s: %s", doc_name, exc)
                print(f"   ❌ [FAILED] {doc_name} — Lỗi: {exc}")

    if success_count > 0:
        print("\n🔄 Đang tái lập chỉ mục BM25 toàn bộ kho tri thức...")
        bm25_start = time.perf_counter()
        total_chunks = indexer.rebuild_bm25_index()
        bm25_elapsed = time.perf_counter() - bm25_start
        print(f"   ✅ Chỉ mục BM25 hoàn tất trong {bm25_elapsed:.2f}s ({total_chunks} chunks toàn corpus).")
    else:
        total_chunks = 0

    elapsed = time.perf_counter() - start_time
    print("\n" + "=" * 60)
    print("📊 BÁO CÁO TỔNG KẾT NẠP DỮ LIỆU:")
    print(f"   - Tổng số tệp quét được: {len(candidate_files)}")
    print(f"   - Nạp thành công (READY): {success_count}")
    print(f"   - Bỏ qua (trùng lặp):     {skipped_count}")
    print(f"   - Thất bại (FAILED):      {fail_count + len(error_results)}")
    print(f"   - Tổng thời gian:         {elapsed:.2f} giây")
    print("=" * 60)

    return {
        "success": fail_count == 0,
        "total": len(candidate_files),
        "accepted": len(accepted_docs),
        "ingested": success_count,
        "skipped": skipped_count,
        "failed": fail_count + len(error_results),
        "elapsed_seconds": round(elapsed, 2),
    }


def main():
    """CLI entry point for ingesting a folder of documents."""
    parser = argparse.ArgumentParser(description="Legal CRAG Assistant — Folder Ingestion CLI")
    parser.add_argument("folder", type=str, help="Đường dẫn thư mục chứa tài liệu cần nạp")
    parser.add_argument("--replace", action="store_true", help="Ghi đè và nạp lại nếu tệp đã tồn tại trong hệ thống")
    parser.add_argument("--no-recursive", action="store_true", help="Chỉ quét thư mục hiện tại, không quét thư mục con")
    parser.add_argument("--workers", type=int, default=None, help="Số luồng xử lý đồng thời (mặc định: INGESTION_WORKERS)")
    args = parser.parse_args()

    result = ingest_folder(
        folder_path=args.folder,
        replace=args.replace,
        recursive=not args.no_recursive,
        max_workers=args.workers,
    )
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()

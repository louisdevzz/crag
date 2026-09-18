"""System initialization and environment diagnostic script for the Legal CRAG Assistant."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    CHROMA_DIR,
    CONFIG,
    CRAG_HOME,
    DB_PATH,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LLM_MODEL,
    LLM_PROVIDER,
    RERANKER_MODEL,
)
from create_db import EXPECTED_TABLES, init_db, verify_db
from logging_config import get_logger

log = get_logger("init_system")


def init_system(
    check_models: bool = False,
    reset: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Execute complete system initialization and diagnostics."""
    start_time = time.time()
    results: Dict[str, Any] = {
        "crag_home": str(CRAG_HOME),
        "db_path": str(DB_PATH),
        "chroma_dir": str(CHROMA_DIR),
        "directories_created": [],
        "database_status": "unknown",
        "migrated_from_legacy": False,
        "tables": {},
        "env_status": "ok",
        "models_status": "skipped",
    }

    if not quiet:
        print("=" * 80)
        print("LEGAL CRAG ASSISTANT — SYSTEM INITIALIZATION & DIAGNOSTICS")
        print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Directory Structure Setup
    # -------------------------------------------------------------------------
    if not quiet:
        print(f"\n📁 [1/4] Khởi tạo cấu trúc thư mục hệ thống tại: {CRAG_HOME}")

    required_dirs = [
        CRAG_HOME,
        CRAG_HOME / "database",
        CRAG_HOME / "chroma",
        CRAG_HOME / "logs",
        CHROMA_DIR,
        DB_PATH.parent,
    ]

    for d in required_dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            results["directories_created"].append(str(d))
            if not quiet:
                print(f"   ➕ Đã tạo thư mục: {d}")
        else:
            if not quiet:
                print(f"   ✔ Thư mục đã tồn tại: {d}")

    # -------------------------------------------------------------------------
    # 2. Database Initialization & Legacy Migration
    # -------------------------------------------------------------------------
    if not quiet:
        print(f"\n🗄️  [2/4] Khởi tạo cơ sở dữ liệu SQLite tại: {DB_PATH}")

    # Check for legacy app.db in project root
    legacy_db = PROJECT_ROOT / "app.db"
    if legacy_db.exists() and legacy_db.resolve() != DB_PATH.resolve() and not DB_PATH.exists():
        if not quiet:
            print(f"   🔄 Phát hiện database cũ tại repo root ({legacy_db}), đang chuyển sang {DB_PATH}...")
        try:
            shutil.copy2(legacy_db, DB_PATH)
            results["migrated_from_legacy"] = True
            if not quiet:
                print(f"   ✔ Đã sao chép database cũ thành công sang {DB_PATH}")
        except Exception as e:
            if not quiet:
                print(f"   ⚠️ Không thể sao chép database cũ ({e}), tiến hành khởi tạo mới.")

    if reset and DB_PATH.exists():
        if not quiet:
            print(f"   ⚠️ Đang reset database theo yêu cầu: {DB_PATH}")
        # Remove DB and journal/wal/shm files
        for suffix in ["", "-wal", "-shm", "-journal"]:
            f = Path(str(DB_PATH) + suffix)
            if f.exists():
                f.unlink()

    # Initialize tables via schema.sql
    try:
        init_db(db_path=DB_PATH, quiet=True)
        table_counts = verify_db(db_path=DB_PATH)
        results["database_status"] = "ready"
        results["tables"] = table_counts
        if not quiet:
            print(f"   ✔ SQLite schema hợp lệ ({len(table_counts)}/{len(EXPECTED_TABLES)} bảng):")
            for tbl, count in table_counts.items():
                print(f"      - {tbl:22s}: {count:5d} bản ghi")
    except Exception as e:
        results["database_status"] = f"error: {e}"
        if not quiet:
            print(f"   ❌ Lỗi khởi tạo database: {e}")
        raise

    # -------------------------------------------------------------------------
    # 3. Environment & Configuration Check
    # -------------------------------------------------------------------------
    if not quiet:
        print("\n⚙️  [3/4] Kiểm tra biến môi trường và cấu hình trung tâm")

    env_file = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"
    if not env_file.exists() and env_example.exists():
        if not quiet:
            print("   ⚠️ Không tìm thấy .env, đang tự động sao chép từ .env.example...")
        shutil.copy2(env_example, env_file)
        results["env_created"] = True

    if not quiet:
        print(f"   ✔ LLM Provider:       {LLM_PROVIDER} (Model: {LLM_MODEL})")
        print(f"   ✔ Embedding Model:    {EMBEDDING_MODEL} (Provider: {EMBEDDING_PROVIDER})")
        print(f"   ✔ Reranker Model:     {RERANKER_MODEL}")
        print(f"   ✔ CRAG Thresholds:    T_LOW={CONFIG.crag.t_low}, T_HIGH={CONFIG.crag.t_high}")
        print(f"   ✔ Database Path:      {DB_PATH}")
        print(f"   ✔ Chroma Directory:   {CHROMA_DIR}")

    # -------------------------------------------------------------------------
    # 4. Model Pre-flight Check (Optional)
    # -------------------------------------------------------------------------
    if check_models:
        if not quiet:
            print("\n🤖 [4/4] Kiểm tra tải trước mô hình Embedding & Reranker...")
        try:
            from scripts.pull_models import pull_huggingface_model
            emb_ok = pull_huggingface_model(EMBEDDING_MODEL, verify_type="embedding")
            rerank_ok = pull_huggingface_model(RERANKER_MODEL, verify_type="reranker")
            results["models_status"] = "ok" if (emb_ok and rerank_ok) else "partial_failure"
        except Exception as e:
            results["models_status"] = f"error: {e}"
            if not quiet:
                print(f"   ⚠️ Lỗi kiểm tra model: {e}")
    else:
        results["models_status"] = "skipped (chạy --check-models để tải và kiểm tra)"
        if not quiet:
            print("\n🤖 [4/4] Kiểm tra mô hình: Bỏ qua (dùng --check-models để tải trước)")

    elapsed = time.time() - start_time
    if not quiet:
        print("\n" + "=" * 80)
        print(f"✅ KHỞI TẠO HỆ THỐNG THÀNH CÔNG trong {elapsed:.2f}s!")
        print(f"   Database:  {DB_PATH}")
        print(f"   Chroma:    {CHROMA_DIR}")
        print("=" * 80)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Legal CRAG Assistant System Initialization & Diagnostic Tool")
    parser.add_argument(
        "--check-models",
        action="store_true",
        help="Download and verify Hugging Face embedding and reranker model weights",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe and cleanly reinitialize the SQLite database at DB_PATH",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )
    args = parser.parse_args()

    init_system(
        check_models=args.check_models,
        reset=args.reset,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()

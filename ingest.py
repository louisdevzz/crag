"""Ingestion Pipeline for Legal CRAG Assistant V3.

Populates:
1. SQLite Database (`app.db`): `legal_documents`, `provisions`, `provision_versions`.
2. BM25 Lexical Index (`data/processed/bm25_index.pkl`).
3. Chroma Dense Vector Store (`./chroma` collection `legal_corpus_v1`).
"""
from __future__ import annotations

import json
import pickle
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from rank_bm25 import BM25Okapi

from config import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    DATA_DIR,
    DB_PATH,
    PROCESSED_DATA_DIR,
)
from create_db import init_db
from legal.preprocessor import UniversalLegalPreprocessor
from llm import get_embeddings


def tokenize_vi(text: str) -> List[str]:
    """Tokenize Vietnamese text for lexical BM25 matching."""
    cleaned = text.lower().replace(",", " ").replace(".", " ").replace(";", " ").replace(":", " ")
    return [w for w in cleaned.split() if len(w) > 1]


def ingest_corpus(
    data_dir: Path | str = DATA_DIR,
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
    rebuild_preprocessed: bool = False,
) -> Dict[str, Any]:
    """Run full ingestion pipeline."""
    data_dir = Path(data_dir)
    db_path = Path(db_path)
    chroma_dir = Path(chroma_dir)

    print("=" * 70)
    print("LEGAL CRAG ASSISTANT V3 — INGESTION PIPELINE")
    print("=" * 70)

    # 1. Initialize SQLite Database
    init_db(db_path)

    # 2. Check or run preprocessor
    processed_files = list(PROCESSED_DATA_DIR.glob("*.json"))
    # Exclude manifest or index json files
    doc_json_files = [f for f in processed_files if f.name != "corpus_manifest.json"]

    if not doc_json_files or rebuild_preprocessed:
        print("\n--- Step 1: Running Universal Preprocessor on data/ ---")
        preprocessor = UniversalLegalPreprocessor(enable_vision_ocr=False)
        preprocessor.process_all(data_dir)
        doc_json_files = [f for f in PROCESSED_DATA_DIR.glob("*.json") if f.name != "corpus_manifest.json"]

    print(f"\n--- Step 2: Ingesting {len(doc_json_files)} processed legal documents into SQLite ---")
    all_provisions: List[Dict[str, Any]] = []
    total_docs = 0

    with sqlite3.connect(db_path) as con:
        cur = con.cursor()

        for jf in doc_json_files:
            data = json.loads(jf.read_text(encoding="utf-8"))
            meta = data.get("metadata", {})
            provisions = data.get("provisions", [])

            if not meta.get("id"):
                continue

            total_docs += 1
            cur.execute(
                """
                INSERT OR REPLACE INTO legal_documents (
                    id, document_number, title, document_type, issuing_authority,
                    issued_at, effective_from, effective_to, status, source_url, retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    meta["id"],
                    meta.get("document_number", meta["id"]),
                    meta.get("title", meta["id"]),
                    meta.get("document_type", "Văn bản"),
                    meta.get("issuing_authority", ""),
                    meta.get("issued_at"),
                    meta.get("effective_from"),
                    meta.get("effective_to"),
                    meta.get("status", "effective"),
                    meta.get("source_url", ""),
                ),
            )

            # Insert provisions
            for p in provisions:
                p_id = p.get("id") or p.get("locator")
                cur.execute(
                    """
                    INSERT OR REPLACE INTO provisions (
                        id, document_id, chapter, article, clause, point, heading, text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p_id,
                        meta["id"],
                        p.get("chapter", ""),
                        p.get("article", ""),
                        p.get("clause", ""),
                        p.get("point", ""),
                        p.get("heading", ""),
                        p.get("text", ""),
                    ),
                )
                all_provisions.append({
                    "evidence_id": p_id,
                    "locator": p_id,
                    "document_id": meta["id"],
                    "document_number": meta.get("document_number", meta["id"]),
                    "document_title": meta.get("title", meta["id"]),
                    "chapter": p.get("chapter", ""),
                    "article": p.get("article", ""),
                    "clause": p.get("clause", ""),
                    "heading": p.get("heading", ""),
                    "text": p.get("text", ""),
                    "provenance": p.get("provenance", f"{meta.get('title')} > {p.get('article')}"),
                    "source_priority": 2,  # Official internal corpus = high priority
                })

        con.commit()

    print(f"SQLite ingestion complete: {total_docs} documents, {len(all_provisions)} provisions.")

    # 3. Build & Serialize BM25 Lexical Index
    print("\n--- Step 3: Building BM25 Lexical Index ---")
    tokenized_corpus = [tokenize_vi(p["text"] + " " + p.get("heading", "")) for p in all_provisions]
    bm25 = BM25Okapi(tokenized_corpus)

    bm25_data = {
        "bm25": bm25,
        "provisions": all_provisions,
        "count": len(all_provisions),
    }
    bm25_path = PROCESSED_DATA_DIR / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25_data, f)
    print(f"BM25 index serialized to {bm25_path} ({len(all_provisions)} items indexed).")

    # 4. Build & Persist Chroma Dense Vector Index
    print("\n--- Step 4: Building Chroma Dense Vector Index ---")
    chroma_dir.mkdir(parents=True, exist_ok=True)
    embeddings = get_embeddings()

    from langchain_chroma import Chroma

    # Delete existing collection if present to avoid duplication
    vectorstore = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir),
    )

    # Ingest in batches to avoid memory spikes
    batch_size = 100
    texts = [p["text"] for p in all_provisions]
    metadatas = [
        {
            "evidence_id": p["evidence_id"],
            "locator": p["locator"],
            "document_id": p["document_id"],
            "document_number": p["document_number"],
            "document_title": p["document_title"],
            "chapter": p.get("chapter", ""),
            "article": p.get("article", ""),
            "clause": p.get("clause", ""),
            "heading": p.get("heading", ""),
        }
        for p in all_provisions
    ]
    ids = [p["evidence_id"] for p in all_provisions]

    print(f"Adding {len(texts)} provisions to Chroma collection '{CHROMA_COLLECTION}'...")
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        vectorstore.add_texts(
            texts=batch_texts,
            metadatas=batch_metas,
            ids=batch_ids,
        )
        print(f"  Indexed items {i + 1} to {min(i + batch_size, len(texts))} / {len(texts)}")

    print(f"Chroma dense vector index ready at {chroma_dir}")
    print("\n" + "=" * 70)
    print("INGESTION SUCCESSFULLY COMPLETED!")
    print(f"Summary: {total_docs} Documents | {len(all_provisions)} Provisions in SQLite, BM25, and Chroma")
    print("=" * 70)

    return {
        "total_documents": total_docs,
        "total_provisions": len(all_provisions),
        "db_path": str(db_path),
        "bm25_path": str(bm25_path),
        "chroma_dir": str(chroma_dir),
    }


if __name__ == "__main__":
    ingest_corpus()

"""Ingestion Pipeline for Legal CRAG Assistant.

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


def get_vectorstore(chroma_dir: Path | str = CHROMA_DIR):
    """Return the Chroma dense vectorstore handle, creating the directory if needed."""
    from langchain_chroma import Chroma

    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(chroma_dir),
    )


def rebuild_bm25_index(db_path: Path | str = DB_PATH) -> int:
    """Rebuild the BM25 lexical index from the current `provisions` table in SQLite.

    Always the single source of truth for the BM25 index, called after any insert or
    delete so the lexical index never drifts from SQLite.
    """
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT p.id AS evidence_id, p.document_id, p.chapter, p.article, p.clause,
                   p.heading, p.text, d.document_number, d.title AS document_title
            FROM provisions p
            JOIN legal_documents d ON d.id = p.document_id
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    all_provisions = [
        {
            "evidence_id": r["evidence_id"],
            "locator": r["evidence_id"],
            "document_id": r["document_id"],
            "document_number": r["document_number"],
            "document_title": r["document_title"],
            "chapter": r.get("chapter", ""),
            "article": r.get("article", ""),
            "clause": r.get("clause", ""),
            "heading": r.get("heading", ""),
            "text": r["text"],
            "provenance": f"{r['document_title']} > {r.get('article', '')}",
            "source_priority": 2,
        }
        for r in rows
    ]

    tokenized_corpus = [tokenize_vi(p["text"] + " " + p.get("heading", "")) for p in all_provisions]
    bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else BM25Okapi([[""]])
    bm25_data = {"bm25": bm25, "provisions": all_provisions, "count": len(all_provisions)}

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    bm25_path = PROCESSED_DATA_DIR / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25_data, f)
    return len(all_provisions)


def rebuild_chroma_index(
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
    batch_size: int = 64,
) -> int:
    """Rebuild the Chroma dense vector index from the current `provisions` table.

    A collection's embedding dimension is fixed at creation time, so changing
    `EMBEDDING_MODEL` (e.g. a 384-dim model -> BAAI/bge-m3 at 1024-dim) leaves
    the persisted collection stale: queries then raise `InvalidArgumentError`
    ("expecting embedding with dimension of 384, got 1024"). SQLite is the
    single source of truth for provisions (see `rebuild_bm25_index`), so this
    drops and recreates the collection and re-embeds every provision from
    there — no raw source documents required.
    """
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT p.id AS evidence_id, p.document_id, p.chapter, p.article, p.clause,
                   p.heading, p.text, d.document_number, d.title AS document_title
            FROM provisions p
            JOIN legal_documents d ON d.id = p.document_id
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    vectorstore = get_vectorstore(chroma_dir)
    try:
        vectorstore.delete_collection()
    except Exception:
        pass
    vectorstore = get_vectorstore(chroma_dir)  # recreate empty, bound to the current embedding function

    if not rows:
        return 0

    texts = [r["text"] for r in rows]
    ids = [r["evidence_id"] for r in rows]
    metadatas = [
        {
            "evidence_id": r["evidence_id"],
            "locator": r["evidence_id"],
            "document_id": r["document_id"],
            "document_number": r["document_number"],
            "document_title": r["document_title"],
            "chapter": r.get("chapter") or "",
            "article": r.get("article") or "",
            "clause": r.get("clause") or "",
            "heading": r.get("heading") or "",
        }
        for r in rows
    ]

    for i in range(0, len(texts), batch_size):
        vectorstore.add_texts(
            texts=texts[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
            ids=ids[i : i + batch_size],
        )

    return len(rows)


def add_document_to_indexes(
    result: Dict[str, Any],
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
) -> Dict[str, Any]:
    """Ingest one preprocessed document (from `UniversalLegalPreprocessor.process_file`)
    into SQLite, Chroma, and rebuild BM25. Used by the Admin upload endpoint for
    incremental single-document ingestion without rebuilding the whole corpus.
    """
    db_path = Path(db_path)
    meta = result["metadata"]
    provisions = result.get("provisions", [])
    if not meta.get("id"):
        raise ValueError("Preprocessed document is missing a stable 'id' in its metadata")

    init_db(db_path)

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        cur = con.cursor()
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
        # Re-uploading the same document replaces its provisions rather than duplicating them.
        cur.execute("DELETE FROM provisions WHERE document_id = ?", (meta["id"],))
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
        con.commit()

    # Sync Chroma: drop any stale vectors for this document_id, then add the fresh ones.
    vectorstore = get_vectorstore(chroma_dir)
    try:
        existing = vectorstore.get(where={"document_id": meta["id"]})
        if existing and existing.get("ids"):
            vectorstore.delete(ids=existing["ids"])
    except Exception:
        pass

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []
    for p in provisions:
        p_id = p.get("id") or p.get("locator")
        texts.append(p.get("text", ""))
        metadatas.append(
            {
                "evidence_id": p_id,
                "locator": p_id,
                "document_id": meta["id"],
                "document_number": meta.get("document_number", meta["id"]),
                "document_title": meta.get("title", meta["id"]),
                "chapter": p.get("chapter", ""),
                "article": p.get("article", ""),
                "clause": p.get("clause", ""),
                "heading": p.get("heading", ""),
            }
        )
        ids.append(p_id)

    if texts:
        vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    corpus_total = rebuild_bm25_index(db_path)

    return {
        "document_id": meta["id"],
        "document_number": meta.get("document_number", meta["id"]),
        "title": meta.get("title", meta["id"]),
        "provisions_count": len(provisions),
        "strips_count": result.get("strips_count", len(result.get("strips", []))),
        "corpus_total_provisions": corpus_total,
    }


def delete_document_from_indexes(
    document_id: str,
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
) -> Dict[str, Any]:
    """Remove a document and all of its provisions from SQLite, Chroma, and rebuild BM25."""
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        cur = con.cursor()
        cur.execute("SELECT document_number FROM legal_documents WHERE id = ?", (document_id,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Document not found: {document_id}")
        document_number = row[0]

        cur.execute("SELECT id FROM provisions WHERE document_id = ?", (document_id,))
        provision_ids = [r[0] for r in cur.fetchall()]

        cur.execute("DELETE FROM legal_documents WHERE id = ?", (document_id,))
        con.commit()

    if provision_ids:
        vectorstore = get_vectorstore(chroma_dir)
        try:
            vectorstore.delete(ids=provision_ids)
        except Exception:
            pass

    corpus_total = rebuild_bm25_index(db_path)

    processed_json = PROCESSED_DATA_DIR / f"{document_id}.json"
    if processed_json.exists():
        processed_json.unlink()

    return {
        "document_id": document_id,
        "document_number": document_number,
        "deleted_provisions": len(provision_ids),
        "corpus_total_provisions": corpus_total,
    }


def ingest_corpus(
    data_dir: Path | str = DATA_DIR,
    db_path: Path | str = DB_PATH,
    chroma_dir: Path | str = CHROMA_DIR,
    rebuild_preprocessed: bool = False,
) -> Dict[str, Any]:
    """Run full bulk ingestion pipeline over every document in `data_dir`."""
    data_dir = Path(data_dir)
    db_path = Path(db_path)
    chroma_dir = Path(chroma_dir)

    print("=" * 70)
    print("LEGAL CRAG ASSISTANT — INGESTION PIPELINE")
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
    total_docs = 0
    total_provisions = 0

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
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
                total_provisions += 1

        con.commit()

    print(f"SQLite ingestion complete: {total_docs} documents, {total_provisions} provisions.")

    # 3. Build & Serialize BM25 Lexical Index (single source of truth: SQLite)
    print("\n--- Step 3: Building BM25 Lexical Index ---")
    bm25_count = rebuild_bm25_index(db_path)
    bm25_path = PROCESSED_DATA_DIR / "bm25_index.pkl"
    print(f"BM25 index serialized to {bm25_path} ({bm25_count} items indexed).")

    # 4. Build & Persist Chroma Dense Vector Index
    print("\n--- Step 4: Building Chroma Dense Vector Index ---")
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT p.id AS evidence_id, p.document_id, p.chapter, p.article, p.clause,
                   p.heading, p.text, d.document_number, d.title AS document_title
            FROM provisions p
            JOIN legal_documents d ON d.id = p.document_id
            """
        )
        all_provisions = [dict(r) for r in cur.fetchall()]

    vectorstore = get_vectorstore(chroma_dir)

    batch_size = 100
    texts = [p["text"] for p in all_provisions]
    metadatas = [
        {
            "evidence_id": p["evidence_id"],
            "locator": p["evidence_id"],
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

"""Database Initialization Script for Legal CRAG Assistant."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH

EXPECTED_TABLES = [
    "legal_documents",
    "provisions",
    "provision_versions",
    "legal_relations",
    "clients",
    "chat_sessions",
    "query_logs",
    "client_memories",
]


def verify_db(db_path: Path | str = DB_PATH) -> dict[str, int]:
    """Verify schema integrity and return row count for each expected table."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist at {db_path}")

    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cur.fetchall()}

        missing = set(EXPECTED_TABLES) - existing_tables
        if missing:
            raise RuntimeError(f"Database at {db_path} is missing tables: {missing}")

        for table in EXPECTED_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]

    return counts


def init_db(db_path: Path | str = DB_PATH, quiet: bool = False) -> Path:
    """Initialize SQLite tables and indexes from schema.sql."""
    db_path = Path(db_path)
    schema_file = Path(__file__).resolve().parent / "schema.sql"

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_file}")

    if not quiet:
        print(f"Initializing database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        with open(schema_file, "r", encoding="utf-8") as f:
            con.executescript(f.read())

    if not quiet:
        counts = verify_db(db_path)
        print(f"Database and indexes successfully initialized at: {db_path}")
        print(f"Verified {len(counts)}/{len(EXPECTED_TABLES)} tables.")

    return db_path
if __name__ == "__main__":
    init_db()

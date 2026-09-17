"""Database Initialization Script for Legal CRAG Assistant."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH

# Columns added to `ingestion_jobs` after its original release. `CREATE TABLE
# IF NOT EXISTS` (via schema.sql) never alters an already-existing table, so
# an app.db created before these columns existed needs this explicit,
# idempotent `ALTER TABLE ... ADD COLUMN` migration on every startup.
_INGESTION_JOBS_MIGRATIONS = [
    ("detail", "TEXT"),
    ("processed_units", "INTEGER NOT NULL DEFAULT 0"),
    ("total_units", "INTEGER NOT NULL DEFAULT 0"),
]


def _migrate_columns(con: sqlite3.Connection) -> None:
    """Add any `ingestion_jobs` columns missing from an already-existing table."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(ingestion_jobs)")}
    for name, ddl_type in _INGESTION_JOBS_MIGRATIONS:
        if name not in existing:
            con.execute(f"ALTER TABLE ingestion_jobs ADD COLUMN {name} {ddl_type}")


EXPECTED_TABLES = [
    "documents",
    "document_chunks",
    "legal_relations",
    "ingestion_jobs",
    "clients",
    "sessions",
    "messages",
    "memories",
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
        _migrate_columns(con)
        con.commit()

    if not quiet:
        counts = verify_db(db_path)
        print(f"Database and indexes successfully initialized at: {db_path}")
        print(f"Verified {len(counts)}/{len(EXPECTED_TABLES)} tables.")

    return db_path


if __name__ == "__main__":
    init_db()

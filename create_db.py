"""Database Initialization Script for Legal CRAG Assistant."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Initialize SQLite tables and indexes from schema.sql."""
    db_path = Path(db_path)
    schema_file = Path(__file__).resolve().parent / "schema.sql"

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_file}")

    print(f"Initializing database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        with open(schema_file, "r", encoding="utf-8") as f:
            con.executescript(f.read())

    print(f"Database and indexes successfully initialized at: {db_path}")


if __name__ == "__main__":
    init_db()

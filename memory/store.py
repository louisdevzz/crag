"""Session Memory Store with 3-Tier Hierarchy and Client Isolation Guardrail."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from config import ALLOWED_MEMORY_KEYS, DB_PATH


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


class MemoryStore:
    """Manages Client Profiles, Session Tracking, Episodic Query Logs, and Semantic Memory."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)

    def get_or_create_client(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch or initialize an anonymous client record."""
        cid = client_id.strip() if client_id and client_id.strip() else f"client_{uuid.uuid4().hex[:12]}"
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT id, memory_enabled, created_at, last_seen_at FROM clients WHERE id = ?", (cid,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE clients SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))
                con.commit()
                return dict(row)
            else:
                cur.execute(
                    "INSERT INTO clients (id, memory_enabled, created_at, last_seen_at) VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (cid,),
                )
                con.commit()
                return {"id": cid, "memory_enabled": 1}

    def create_session(self, client_id: str, session_id: Optional[str] = None) -> str:
        """Create or register a chat session under a client."""
        self.get_or_create_client(client_id)
        sid = session_id.strip() if session_id and session_id.strip() else f"sess_{uuid.uuid4().hex[:12]}"
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT id FROM chat_sessions WHERE id = ? AND client_id = ?", (sid, client_id))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO chat_sessions (id, client_id, started_at, last_active_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (sid, client_id),
                )
                con.commit()
            else:
                cur.execute("UPDATE chat_sessions SET last_active_at = CURRENT_TIMESTAMP WHERE id = ?", (sid,))
                con.commit()
        return sid

    def log_query(
        self,
        client_id: str,
        session_id: str,
        question: str,
        answer: str,
        route: str = "rag",
        crag_action: str = "CORRECT",
        source_type: Optional[str] = None,
    ) -> int:
        """Log an episodic query event (Tier 2: Episodic Memory / Audit Log)."""
        self.create_session(client_id, session_id)
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO query_logs (client_id, session_id, question, answer, route, crag_action, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (client_id, session_id, question, answer, route, crag_action, source_type),
            )
            con.commit()
            return cur.lastrowid

    def get_query_history(self, client_id: str, session_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent query turns strictly scoped to the specified client."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            if session_id:
                cur.execute(
                    """
                    SELECT id, session_id, question, answer, route, crag_action, created_at
                    FROM query_logs
                    WHERE client_id = ? AND session_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (client_id, session_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, session_id, question, answer, route, crag_action, created_at
                    FROM query_logs
                    WHERE client_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (client_id, limit),
                )
            rows = [dict(r) for r in cur.fetchall()]
            rows.reverse()
            return rows

    def get_client_memories(self, client_id: str) -> Dict[str, str]:
        """Fetch all persistent attributes for a client (Tier 3: Semantic Profile)."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT memory_key, memory_value FROM client_memories WHERE client_id = ?",
                (client_id,),
            )
            return {r["memory_key"]: r["memory_value"] for r in cur.fetchall()}

    def set_client_memory(
        self,
        client_id: str,
        memory_key: str,
        memory_value: str,
        confidence: float = 1.0,
    ) -> bool:
        """Save or update a semantic profile attribute, enforcing the strict ALLOWED_MEMORY_KEYS allow-list."""
        key_clean = memory_key.strip().lower()
        if key_clean not in ALLOWED_MEMORY_KEYS:
            print(f"Memory key '{key_clean}' rejected: not in ALLOWED_MEMORY_KEYS.")
            return False

        self.get_or_create_client(client_id)
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO client_memories (client_id, memory_key, memory_value, confidence, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(client_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    confidence = excluded.confidence,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (client_id, key_clean, memory_value.strip(), confidence),
            )
            con.commit()
            return True

    def clear_client_memories(self, client_id: str) -> int:
        """Clear all semantic memory for a client."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM client_memories WHERE client_id = ?", (client_id,))
            con.commit()
            return cur.rowcount

    def format_memory_context(self, client_id: str) -> str:
        """Format semantic memories into a non-legal context string for entity resolution.

        Strict Guardrail (Section 5.2):
        Memory provides context for pronoun and entity resolution only;
        never serves as legal evidence.
        """
        memories = self.get_client_memories(client_id)
        if not memories:
            return ""

        parts = []
        labels = {
            "business_type": "Loại hình doanh nghiệp",
            "industry": "Ngành nghề hoạt động",
            "province": "Địa bàn trụ sở",
            "frequent_topic": "Lĩnh vực quan tâm",
            "preferred_answer": "Phong cách trả lời",
        }
        for k, v in memories.items():
            lbl = labels.get(k, k)
            parts.append(f"- {lbl}: {v}")

        return "\n".join(parts)


_GLOBAL_MEMORY_STORE: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _GLOBAL_MEMORY_STORE
    if _GLOBAL_MEMORY_STORE is None:
        _GLOBAL_MEMORY_STORE = MemoryStore()
    return _GLOBAL_MEMORY_STORE

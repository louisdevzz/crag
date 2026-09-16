"""Session, Message and Semantic Memory Store — the single source of truth the
Agent Runtime's Context Manager reads from and writes to every turn.

Three tables (see schema.sql):
- `sessions`    — one row per chat thread, owned by a `clients` row.
- `messages`    — canonical short-term conversational history (user + assistant
                  rows per turn). Read back by `agent.context.build_context` so
                  follow-up questions actually see prior turns.
- `memories`    — long-term semantic profile, strictly governed by the
                  `ALLOWED_MEMORY_KEYS` allow-list. Never legal grounding, only
                  entity resolution (e.g. "công ty tôi" -> business_type/province).
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import ALLOWED_MEMORY_KEYS, DB_PATH


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        from create_db import init_db
        init_db(path, quiet=True)
    con = sqlite3.connect(str(path), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


class MemoryStore:
    """Manages Client Profiles, Session Tracking, Conversational History, and Semantic Memory."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------ clients
    def get_or_create_client(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch or initialize an anonymous client record."""
        cid = (client_id or "").strip() or f"client_{uuid.uuid4().hex[:12]}"
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT id, memory_enabled, created_at, last_seen_at FROM clients WHERE id = ?", (cid,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE clients SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))
                con.commit()
                return dict(row)
            cur.execute(
                "INSERT INTO clients (id, memory_enabled, created_at, last_seen_at) VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (cid,),
            )
            con.commit()
            return {"id": cid, "memory_enabled": 1}

    # ------------------------------------------------------------------ sessions
    def create_session(self, client_id: str, session_id: Optional[str] = None) -> str:
        """Create or touch a chat session under a client."""
        self.get_or_create_client(client_id)
        sid = session_id.strip() if session_id and session_id.strip() else f"sess_{uuid.uuid4().hex[:12]}"
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT id FROM sessions WHERE id = ? AND client_id = ?", (sid, client_id))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO sessions (id, client_id, started_at, last_active_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (sid, client_id),
                )
            else:
                cur.execute("UPDATE sessions SET last_active_at = CURRENT_TIMESTAMP WHERE id = ?", (sid,))
            con.commit()
        return sid

    # ------------------------------------------------------------------ messages (short-term memory)
    def log_message(
        self,
        client_id: str,
        session_id: str,
        role: str,
        content: str,
        route: Optional[str] = None,
        crag_action: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> int:
        """Persist one conversational turn message (Context Manager's source of truth)."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO messages (session_id, client_id, role, content, route, crag_action, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, client_id, role, content, route, crag_action, source_type),
            )
            con.commit()
            return cur.lastrowid

    def get_recent_messages(self, session_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Last `limit` messages of a session in chronological order — what the Context
        Manager feeds into the answer-generation prompt as `conversation_history`."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT id, session_id, role, content, route, crag_action, created_at
                FROM (
                    SELECT * FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?
                )
                ORDER BY id ASC
                """,
                (session_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_query_history(self, client_id: str, session_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Episodic Q&A view reconstructed from `messages`, preserving the API shape the
        frontend chat sidebar already relies on (`question`/`answer` pairs)."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            if session_id:
                cur.execute(
                    """
                    SELECT id, session_id, role, content, route, crag_action, created_at
                    FROM messages WHERE client_id = ? AND session_id = ? ORDER BY id ASC
                    """,
                    (client_id, session_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id, session_id, role, content, route, crag_action, created_at
                    FROM messages WHERE client_id = ? ORDER BY id ASC
                    """,
                    (client_id,),
                )
            rows = [dict(r) for r in cur.fetchall()]

        items: List[Dict[str, Any]] = []
        pending: Optional[Dict[str, Any]] = None
        for row in rows:
            if row["role"] == "user":
                pending = row
            elif row["role"] == "assistant" and pending is not None:
                items.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "question": pending["content"],
                    "answer": row["content"],
                    "route": row["route"],
                    "crag_action": row["crag_action"],
                    "created_at": row["created_at"],
                })
                pending = None
        items.reverse()  # most recent first, matching the old query_logs ORDER BY id DESC
        return items[:limit]

    # ------------------------------------------------------------------ semantic memory (long-term)
    def get_client_memories(self, client_id: str) -> Dict[str, str]:
        """Fetch all persistent attributes for a client (Semantic Profile)."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT memory_key, memory_value FROM memories WHERE client_id = ?", (client_id,))
            return {r["memory_key"]: r["memory_value"] for r in cur.fetchall()}

    def set_client_memory(
        self,
        client_id: str,
        memory_key: str,
        memory_value: str,
        confidence: float = 1.0,
    ) -> bool:
        """Save or update a semantic profile attribute, enforcing the strict allow-list."""
        if memory_key not in ALLOWED_MEMORY_KEYS:
            return False
        self.get_or_create_client(client_id)
        with get_connection(self.db_path) as con:
            con.execute(
                """
                INSERT INTO memories (client_id, memory_key, memory_value, confidence, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(client_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    confidence = excluded.confidence,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (client_id, memory_key, memory_value, confidence),
            )
            con.commit()
        return True

    def clear_client_memories(self, client_id: str) -> int:
        """Clear all semantic memory for a client."""
        with get_connection(self.db_path) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM memories WHERE client_id = ?", (client_id,))
            con.commit()
            return cur.rowcount

    def format_memory_context(self, client_id: str) -> str:
        """Format semantic memories into a non-legal context string for entity resolution.

        Guardrail: this text is labelled explicitly (in every prompt that consumes it)
        as background only, never as legal grounding — see agent/nodes.py.
        """
        memories = self.get_client_memories(client_id)
        if not memories:
            return ""
        parts = [f"- {k}: {v}" for k, v in memories.items()]
        return "\n".join(parts)


_GLOBAL_MEMORY_STORE: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _GLOBAL_MEMORY_STORE
    if _GLOBAL_MEMORY_STORE is None:
        _GLOBAL_MEMORY_STORE = MemoryStore()
    return _GLOBAL_MEMORY_STORE

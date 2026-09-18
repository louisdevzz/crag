"""Context manager for assembling session history and semantic memory into turn context."""
from __future__ import annotations

from typing import Any, Dict, List

from config import HISTORY_TURNS
from memory.store import get_memory_store


def format_conversation_history(messages: List[Dict[str, Any]]) -> str:
    """Render recent `role`/`content` message rows as a short dialogue transcript."""
    if not messages:
        return ""
    lines = []
    for m in messages:
        speaker = "Người dùng" if m.get("role") == "user" else "Trợ lý"
        lines.append(f"{speaker}: {m.get('content', '')}")
    return "\n".join(lines)


def build_context(client_id: str, session_id: str, history_turns: int = HISTORY_TURNS) -> Dict[str, str]:
    """Load bounded conversation history and semantic memory profile for a turn."""
    store = get_memory_store()
    recent_messages = store.get_recent_messages(session_id, limit=history_turns * 2)
    return {
        "conversation_history": format_conversation_history(recent_messages),
        "memory_context": store.format_memory_context(client_id),
    }

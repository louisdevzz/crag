"""Context Manager: assembles per-turn context from session history and semantic
memory before the Agent Core (LangGraph) runs.

This is the piece that turns `messages`/`memories` (durable SQLite tables) into the
two prompt-facing fields on `AgentState`: `conversation_history` and `memory_context`.
Without it, every turn would be evaluated in isolation — the gap the previous
architecture pass identified in this project (LangGraph's `MemorySaver` checkpointer
was accumulating no reducer-tracked fields, so multi-turn state never actually
carried forward turn to turn).
"""
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
    """Load bounded conversation history plus the semantic memory profile for one turn.

    `history_turns` counts user/assistant pairs; the underlying message log is queried
    for `2 * history_turns` rows so both sides of each pair are included.
    """
    store = get_memory_store()
    recent_messages = store.get_recent_messages(session_id, limit=history_turns * 2)
    return {
        "conversation_history": format_conversation_history(recent_messages),
        "memory_context": store.format_memory_context(client_id),
    }

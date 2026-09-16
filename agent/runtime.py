"""Agent Runtime: the single entry point that owns session resolution, context
assembly, graph invocation, and turn persistence — so the CLI, the eval harness,
and both FastAPI chat endpoints share one turn lifecycle instead of re-implementing
it three times (the previous source of drift between them).

    prepare_turn()  -> resolve client/session, extract memories, build context,
                        assemble the AgentState input dict (Context Manager step)
    <caller invokes the Agent Core graph itself, streaming or not>
    persist_turn()  -> write the user + assistant messages back to SQLite
    invoke_crag()   -> the full non-streaming turn (prepare -> invoke -> persist)
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from agent.context import build_context
from agent.graph import get_crag_app
from agent.nodes import derive_route_and_action
from memory.extractor import extract_and_save_memories
from memory.store import get_memory_store
from monitoring import trace_config


def prepare_turn(
    client_id: Optional[str],
    session_id: Optional[str],
    query: str,
    as_of_date: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Resolve client/session identity and assemble one turn's `AgentState` input.

    Returns (resolved_client_id, resolved_session_id, state_input).
    """
    store = get_memory_store()
    client_record = store.get_or_create_client(client_id)
    resolved_client_id = client_record["id"]
    resolved_session_id = store.create_session(resolved_client_id, session_id)

    # Semantic memory extraction happens before context assembly so this turn's
    # own disclosures (e.g. "công ty tôi ở Long An") are already available to it.
    extract_and_save_memories(resolved_client_id, query)
    context = build_context(resolved_client_id, resolved_session_id)

    state_input: Dict[str, Any] = {
        "client_id": resolved_client_id,
        "session_id": resolved_session_id,
        "query": query,
        "as_of_date": as_of_date,
        "memory_context": context["memory_context"],
        "conversation_history": context["conversation_history"],
    }
    return resolved_client_id, resolved_session_id, state_input


def persist_turn(
    client_id: str,
    session_id: str,
    query: str,
    answer_text: str,
    route: Optional[str] = None,
    crag_action: Optional[str] = None,
    source_type: Optional[str] = None,
) -> None:
    """Write both sides of one turn to the canonical `messages` table."""
    store = get_memory_store()
    store.log_message(client_id, session_id, role="user", content=query)
    store.log_message(
        client_id, session_id, role="assistant", content=answer_text,
        route=route, crag_action=crag_action, source_type=source_type,
    )


def invoke_crag(
    query: str,
    client_id: Optional[str] = None,
    session_id: Optional[str] = None,
    as_of_date: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """Full non-streaming turn: prepare context, run the Agent Core graph, persist."""
    resolved_client_id, resolved_session_id, state_input = prepare_turn(
        client_id, session_id, query, as_of_date
    )
    graph_app = app or get_crag_app()
    config = trace_config(thread_id=resolved_session_id, client_id=resolved_client_id)
    result = graph_app.invoke(state_input, config=config)

    route, action = derive_route_and_action(result.get("tool_trace", []))
    result["route"] = route
    result["crag_action"] = action
    generation = result.get("generation", {})
    evidence = result.get("evidence", [])
    answer_text = generation.get("answer", "")

    persist_turn(
        resolved_client_id, resolved_session_id, query, answer_text,
        route=route, crag_action=action,
        source_type=evidence[0].get("retrieval_source", "internal") if evidence else "none",
    )
    return result

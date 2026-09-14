"""LangFuse Observability Integration for the Legal CRAG Agent.

A single `langfuse.langchain.CallbackHandler` attached to the LangGraph
`config["callbacks"]` at the top-level `app.invoke()`/`app.astream()` call is
enough to trace an entire turn: LangChain propagates the ambient
`RunnableConfig` (callbacks included) via contextvars into every nested
`llm.invoke()`/`llm.stream()` call made inside any node function for that
run, even though individual nodes (router, rewriter, generator, ...) never
see or forward `config` themselves. No per-node instrumentation needed.

Mirrors the `get_chat_model()` graceful-fallback pattern in `llm.py`: missing
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` disables tracing instead of
crashing the agent.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from logging_config import get_logger

log = get_logger(__name__)

_HANDLER: Optional[Any] = None
_CHECKED = False


def get_langfuse_handler() -> Optional[Any]:
    """Return a shared LangFuse `CallbackHandler`, or `None` if not configured."""
    global _HANDLER, _CHECKED
    if _CHECKED:
        return _HANDLER
    _CHECKED = True

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        log.info("LangFuse tracing disabled (LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY not configured)")
        return None

    try:
        from langfuse.langchain import CallbackHandler
        _HANDLER = CallbackHandler()
        log.info("LangFuse tracing ENABLED -> host=%s", os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
    except Exception as e:
        log.error("LangFuse init FAILED (%s) -> tracing disabled", e)
        _HANDLER = None

    return _HANDLER


def trace_config(
    thread_id: str,
    client_id: Optional[str] = None,
    trace_name: str = "legal-crag-turn",
) -> dict:
    """Build the LangGraph `config` dict for one turn, with LangFuse tracing attached
    when configured. Always includes the `thread_id` for checkpointer continuity;
    tracing is a pure add-on that never blocks a turn when disabled/misconfigured.
    """
    config: dict = {"configurable": {"thread_id": thread_id}}

    handler = get_langfuse_handler()
    if handler is not None:
        config["callbacks"] = [handler]
        config["metadata"] = {
            "langfuse_session_id": thread_id,
            "langfuse_user_id": client_id or "anonymous",
            "langfuse_trace_name": trace_name,
        }
    return config

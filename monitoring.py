"""LangFuse observability integration for the Legal CRAG agent."""
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
    """Build the LangGraph config dictionary for a turn with LangFuse tracing when configured."""
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

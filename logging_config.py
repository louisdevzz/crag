"""Structured pipeline logging for the Legal CRAG Assistant.

Every stage of a turn (routing, embedding/retrieval, reranking, CRAG branch
decision, web search, LLM generation, citation validation) logs a single,
greppable INFO line prefixed `[CRAG:<stage>]` so it's possible to confirm from
the server console — not just trust — that each stage genuinely executed
against a real backend (embedding model, reranker, LLM provider) rather than
a fallback/mocked path.

Usage: `from logging_config import get_logger; log = get_logger(__name__)`.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_name = os.getenv("CRAG_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("crag")
    root.setLevel(level)
    root.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-5s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a `crag.<name>` logger writing greppable pipeline-stage lines."""
    _configure_once()
    short = name.rsplit(".", 1)[-1]
    return logging.getLogger(f"crag.{short}")

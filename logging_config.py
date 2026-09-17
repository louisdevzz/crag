"""Structured pipeline logging for the Legal CRAG Assistant.

Every stage of a turn (routing, embedding/retrieval, reranking, CRAG branch
decision, web search, LLM generation, citation validation) logs a single,
greppable INFO line prefixed `[CRAG:<stage>]` so it's possible to confirm from
the server console — not just trust — that each stage genuinely executed
against a real backend (embedding model, reranker, LLM provider) rather than
a fallback/mocked path.

`timed_stage` extends this to *how long* each stage/sub-step took (LLM call,
dense/BM25 retrieval, rerank, ingestion OCR page, embedding batch, ...) — the
missing piece for diagnosing a slow chat turn or a slow multi-page ingestion
run straight from the console instead of guessing.

Usage: `from logging_config import get_logger, timed_stage; log = get_logger(__name__)`.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

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


@contextmanager
def timed_stage(log: logging.Logger, label: str, **fields: Any) -> Iterator[None]:
    """Log `label`'s start immediately, then its wall-clock duration (plus any
    `key=value` context, e.g. `document=doc_id page=3/45`) on exit — success or
    exception — so a slow request/ingestion run is diagnosable straight from
    the console instead of only from an eventual stage-level timestamp.
    """
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    suffix = f" {extra}" if extra else ""
    log.info("[%s] start%s", label, suffix)
    start = time.perf_counter()
    try:
        yield
    except Exception:
        log.exception("[%s] FAILED after %.3fs%s", label, time.perf_counter() - start, suffix)
        raise
    else:
        log.info("[%s] done in %.3fs%s", label, time.perf_counter() - start, suffix)

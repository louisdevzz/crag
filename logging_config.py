"""Structured pipeline logging and timing utilities for the Legal CRAG Assistant."""
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
    """Context manager to log the start and wall-clock execution duration of a stage."""
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

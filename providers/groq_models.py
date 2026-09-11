"""Dynamic Groq Model Discovery and Free Model Resolver.

Fetches live available models from Groq API, filters active free-tier models,
and prioritizes Qwen 3.8 27B (qwen/qwen3.8-27b) as the primary reasoning/coding
model, per Groq's Free Plan catalog effective 2026-09-11. Older models such as
llama-3.1-8b-instant, llama-3.3-70b-versatile, qwen-2.5-32b and qwen-qwq-32b
were deprecated from Groq's free/developer tier in Jul-Aug 2026 and are no
longer requested.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Current Groq Free Plan catalog (2026-09-11), in preference order.
# qwen/qwen3.8-27b is primary: reasoning, coding, academic work, tool use,
# JSON mode and remote MCP support, with local Ollama qwen3.8:latest as its
# natural offline counterpart.
DEFAULT_FREE_MODELS_FALLBACK: List[str] = [
    "qwen/qwen3.8-27b",          # Primary: reasoning, coding, academic (30 RPM / 1,000 RPD / 200K tok/day)
    "openai/gpt-oss-120b",       # Heavy cloud fallback: strong reasoning + built-in web/browser/code tools
    "qwen/qwen3.6-27b",          # Coding, agent, tool calling
    "openai/gpt-oss-20b",        # Faster, lighter than gpt-oss-120b
    "groq/compound",             # Agent: web search + code execution baked in
    "groq/compound-mini",        # Lighter agent variant
]

# Models retired from Groq's free/developer tier (Jul-Aug 2026); never requested.
DEPRECATED_MODELS: frozenset[str] = frozenset({
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "qwen-2.5-32b",
    "qwen-qwq-32b",
    "qwen/qwen3-32b",
    "llama-4-scout",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
})

_CACHED_MODELS: Optional[List[Dict[str, Any]]] = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour cache


def fetch_groq_models(api_key: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch the list of available models from Groq API with caching.

    Parameters
    ----------
    api_key : str, optional
        Groq API key (defaults to GROQ_API_KEY environment variable).
    force_refresh : bool
        If True, bypasses the in-memory cache.

    Returns
    -------
    list of dict
        Model descriptors including id, active status, context window, and owner.
    """
    global _CACHED_MODELS, _CACHE_TIMESTAMP

    now = time.time()
    if not force_refresh and _CACHED_MODELS is not None and (now - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
        return _CACHED_MODELS

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        return []

    try:
        import groq

        client = groq.Groq(api_key=key)
        model_page = client.models.list()
        raw_list = getattr(model_page, "data", model_page)

        models = []
        for m in raw_list:
            model_id = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else str(m))
            active = getattr(m, "active", True)
            owned_by = getattr(m, "owned_by", "")
            context_window = getattr(m, "context_window", 8192)

            if model_id and active and model_id not in DEPRECATED_MODELS:
                models.append({
                    "id": model_id,
                    "active": active,
                    "owned_by": owned_by,
                    "context_window": context_window,
                })

        _CACHED_MODELS = models
        _CACHE_TIMESTAMP = now
        logger.info(f"Successfully fetched {len(models)} active models from Groq API.")
        return models
    except Exception as e:
        logger.warning(f"Failed to fetch live models from Groq: {e}. Using fallback model registry.")
        return []


def list_groq_free_models(api_key: Optional[str] = None) -> List[str]:
    """Return a list of available active free model IDs on Groq (deprecated models excluded)."""
    live_models = fetch_groq_models(api_key=api_key)
    if live_models:
        return [m["id"] for m in live_models]
    return DEFAULT_FREE_MODELS_FALLBACK


def resolve_groq_model(
    requested_model: Optional[str] = None,
    preferred_family: str = "qwen",
    api_key: Optional[str] = None,
) -> str:
    """Dynamically resolve and select the best available free model on Groq.

    Priority logic:
    1. If a specific, non-generic model name is given, use it as-is (unless deprecated,
       in which case it is remapped to the current primary free model).
    2. Otherwise, query live Groq models (cached) and rank them by DEFAULT_FREE_MODELS_FALLBACK
       preference order, so "qwen/qwen3.8-27b" wins over any other Qwen/GPT-OSS variant.
    3. If live discovery is unavailable (no API key / network), fall back to the static
       DEFAULT_FREE_MODELS_FALLBACK list, still headed by "qwen/qwen3.8-27b".

    Parameters
    ----------
    requested_model : str, optional
        Explicit model name or auto-selection trigger ('auto', 'free', 'qwen', 'default').
    preferred_family : str
        Target model family substring to prioritize when no exact fallback match exists
        (default: 'qwen').
    api_key : str, optional
        Groq API key.

    Returns
    -------
    str
        Resolved model ID ready for inference.
    """
    req = (requested_model or os.getenv("LLM_MODEL", "")).strip()

    is_generic = req.lower() in ("", "auto", "free", "qwen", "default")
    if not is_generic and req:
        if req in DEPRECATED_MODELS:
            logger.warning(f"Requested Groq model '{req}' was deprecated; using '{DEFAULT_FREE_MODELS_FALLBACK[0]}' instead.")
        else:
            return req

    available_models = list_groq_free_models(api_key=api_key)

    # 1. Prefer an exact match against the ranked fallback catalog (qwen/qwen3.8-27b first).
    for candidate in DEFAULT_FREE_MODELS_FALLBACK:
        if candidate in available_models:
            return candidate

    # 2. Loose substring match on the requested family (e.g. any remaining Qwen model).
    for m_id in available_models:
        if preferred_family.lower() in m_id.lower():
            return m_id

    # 3. Default safety fallback.
    return available_models[0] if available_models else DEFAULT_FREE_MODELS_FALLBACK[0]

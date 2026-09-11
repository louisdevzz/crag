"""Dynamic Groq Model Discovery and Free Model Resolver.

Fetches live available models from Groq API, filters active free-tier models,
and prioritizes Qwen models (e.g. Qwen 2.5 32B, QwQ 32B) as requested.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Known free-tier models on Groq in preference order
DEFAULT_FREE_MODELS_FALLBACK: List[str] = [
    "qwen-2.5-32b",
    "qwen-qwq-32b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

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

            if model_id and active:
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
    """Return a list of available active free model IDs on Groq."""
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
    1. If a specific model name is explicitly given (and not 'auto' / 'free' / 'qwen'), use it.
    2. Otherwise, query live Groq models.
    3. Filter for active models matching preferred_family ('qwen' -> qwen-2.5-32b, qwen-qwq, etc.).
    4. If found, return the top matching Qwen model.
    5. If no Qwen model is available on Groq, fall back to Llama 3.3 70B or Llama 3.1 8B.

    Parameters
    ----------
    requested_model : str, optional
        Explicit model name or auto-selection trigger ('auto', 'free', 'qwen').
    preferred_family : str
        Target model family to prioritize (default: 'qwen').
    api_key : str, optional
        Groq API key.

    Returns
    -------
    str
        Resolved model ID ready for inference.
    """
    req = (requested_model or os.getenv("LLM_MODEL", "")).strip()

    # If user provided a specific non-generic model, check if it's not a generic alias
    is_generic = req.lower() in ("", "auto", "free", "qwen", "default")
    if not is_generic and req:
        return req

    # Fetch live available models from Groq
    available_models = list_groq_free_models(api_key=api_key)

    # 1. Search for Qwen family models
    if preferred_family.lower() == "qwen":
        for m_id in available_models:
            if "qwen" in m_id.lower():
                return m_id

    # 2. Search for preferred family
    for m_id in available_models:
        if preferred_family.lower() in m_id.lower():
            return m_id

    # 3. Fallback to top available models in priority order
    for fallback in DEFAULT_FREE_MODELS_FALLBACK:
        if fallback in available_models:
            return fallback

    # Default safety fallback
    return available_models[0] if available_models else "qwen-2.5-32b"

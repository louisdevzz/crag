"""Multi-Provider LLM & Embedding Factory for Legal CRAG Agent.

Provides pluggable access to:
- Groq (ultra-low latency LPU inference)
- OpenAI (GPT-4o, GPT-4o-mini)
- OpenRouter (DeepSeek V3/R1, Qwen 2.5 72B, Claude 3.5 Sonnet, etc.)
- Ollama (local on-premise execution)
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from config import (
    CONFIG,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    OLLAMA_BASE_URL,
    OPENROUTER_BASE_URL,
)
from logging_config import get_logger

log = get_logger(__name__)


def get_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs,
) -> BaseChatModel:
    """Factory function to initialize a LangChain BaseChatModel based on provider.

    Parameters
    ----------
    provider : str, optional
        "groq" | "openai" | "openrouter" | "ollama" (defaults to LLM_PROVIDER from config)
    model : str, optional
        Target model name (defaults to LLM_MODEL from config)
    temperature : float, optional
        Sampling temperature (defaults to 0.0 for deterministic legal QA)

    Returns
    -------
    BaseChatModel
        LangChain-compatible chat model instance
    """
    p = (provider or CONFIG.llm.provider).lower().strip()
    m = model or CONFIG.llm.model
    t = CONFIG.llm.temperature if temperature is None else temperature

    try:
        if p == "groq":
            api_key = kwargs.pop("api_key", os.getenv("GROQ_API_KEY"))
            if not api_key:
                log.warning("LLM provider=groq -> NO API KEY configured, falling back to offline synthesis")
                return None
            from providers.groq_models import resolve_groq_model
            resolved_m = resolve_groq_model(requested_model=m, preferred_family="qwen", api_key=api_key)
            from langchain_groq import ChatGroq
            log.info("LLM provider=groq model=%s temperature=%s -> real ChatGroq client initialized", resolved_m, t)
            return ChatGroq(model=resolved_m, temperature=t, api_key=api_key, **kwargs)

        elif p == "openai":
            api_key = kwargs.pop("api_key", os.getenv("OPENAI_API_KEY"))
            if not api_key:
                log.warning("LLM provider=openai -> NO API KEY configured, falling back to offline synthesis")
                return None
            from langchain_openai import ChatOpenAI
            log.info("LLM provider=openai model=%s temperature=%s -> real ChatOpenAI client initialized", m, t)
            return ChatOpenAI(model=m, temperature=t, api_key=api_key, **kwargs)

        elif p == "openrouter":
            api_key = kwargs.pop("api_key", os.getenv("OPENROUTER_API_KEY"))
            if not api_key:
                log.warning("LLM provider=openrouter -> NO API KEY configured, falling back to offline synthesis")
                return None
            from langchain_openai import ChatOpenAI
            base_url = kwargs.pop("base_url", OPENROUTER_BASE_URL)
            log.info(
                "LLM provider=openrouter model=%s temperature=%s base_url=%s -> real client initialized",
                m, t, base_url,
            )
            return ChatOpenAI(
                model=m,
                temperature=t,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        elif p == "ollama":
            from langchain_ollama import ChatOllama
            base_url = kwargs.pop("base_url", OLLAMA_BASE_URL)
            log.info("LLM provider=ollama model=%s base_url=%s -> real client initialized", m, base_url)
            return ChatOllama(model=m, temperature=t, base_url=base_url, **kwargs)

        else:
            log.error("LLM provider=%s is unknown -> falling back to offline synthesis", p)
            return None
    except Exception as e:
        log.error("LLM provider=%s init FAILED (%s) -> falling back to offline synthesis", p, e)
        return None


def get_chat_model_with_fallback(
    temperature: Optional[float] = None,
    **kwargs,
) -> BaseChatModel:
    """Provider Manager: try `CONFIG.llm.provider` first, then each of
    `CONFIG.llm.fallback_providers` in order, returning the first client that
    initializes successfully (has credentials and constructs without error).

    This only covers *initialization* failures (missing API key, import error,
    unknown provider) — a provider that initializes but fails mid-request still
    falls back to the deterministic evidence-synthesis path in `agent/nodes.py`,
    not to a different provider, since retrying a different provider mid-stream
    would require re-issuing the whole request.
    """
    tried = []
    candidates = [CONFIG.llm.provider] + [p for p in CONFIG.llm.fallback_providers if p != CONFIG.llm.provider]
    for provider in candidates:
        tried.append(provider)
        model = get_chat_model(provider=provider, temperature=temperature, **kwargs)
        if model is not None:
            if provider != CONFIG.llm.provider:
                log.warning("Provider Manager: primary=%s unavailable -> fell back to provider=%s", CONFIG.llm.provider, provider)
            return model
    log.error("Provider Manager: every candidate provider failed to initialize (%s) -> no LLM available", tried)
    return None

_EMBEDDINGS_CACHE: Dict[tuple, Any] = {}
_EMBEDDINGS_LOCK = threading.Lock()


def get_embeddings(provider: Optional[str] = None, model: Optional[str] = None):
    """Cached factory for real text embedding models — the underlying client (e.g.
    HuggingFaceEmbeddings, which loads a multi-hundred-MB transformer from disk into
    memory) is expensive to construct, so every (provider, model) pair is built at
    most once per process and reused across every `crag_search` call and ingestion
    run, mirroring `retrieval.reranker`'s singleton pattern. Thread-safe: FastAPI runs
    sync request handlers in a threadpool, so concurrent first requests could
    otherwise race to construct (and load) the model twice.
    """
    p = (provider or os.getenv("EMBEDDING_PROVIDER") or EMBEDDING_PROVIDER).lower().strip()
    m = model or os.getenv("EMBEDDING_MODEL") or EMBEDDING_MODEL
    key = (p, m)
    cached = _EMBEDDINGS_CACHE.get(key)
    if cached is not None:
        return cached
    with _EMBEDDINGS_LOCK:
        cached = _EMBEDDINGS_CACHE.get(key)
        if cached is not None:
            return cached
        instance = _build_embeddings(p, m)
        _EMBEDDINGS_CACHE[key] = instance
        return instance


def _build_embeddings(p: str, m: str):
    """One-time construction of the embedding client for `(p, m)`; see `get_embeddings`."""
    if p in ("huggingface", "sentence-transformers"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            log.info("Embeddings provider=%s model=%s -> initializing HuggingFaceEmbeddings", p, m)
            return HuggingFaceEmbeddings(
                model_name=m,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as e:
            log.error("Failed to load HuggingFace embedding model '%s': %s", m, e)
            raise RuntimeError(
                f"Không thể khởi tạo mô hình embedding '{m}' từ Hugging Face: {e}\n"
                f"Vui lòng chạy script: 'python scripts/pull_models.py --embedding' "
                f"để tải sẵn trọng số mô hình về máy."
            ) from e

    elif p == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your_"):
            raise ValueError(
                "EMBEDDING_PROVIDER='openai' nhưng chưa cấu hình OPENAI_API_KEY hợp lệ trong file .env."
            )
        try:
            from langchain_openai import OpenAIEmbeddings
            log.info("Embeddings provider=openai model=%s -> initializing OpenAIEmbeddings", m)
            return OpenAIEmbeddings(model=m, api_key=api_key)
        except Exception as e:
            log.error("Failed to load OpenAI embedding model '%s': %s", m, e)
            raise RuntimeError(f"Lỗi khởi tạo OpenAIEmbeddings: {e}") from e

    elif p == "ollama":
        try:
            import requests
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama server trả về mã lỗi HTTP {resp.status_code}")
            from langchain_ollama import OllamaEmbeddings
            log.info("Embeddings provider=ollama model=%s base_url=%s -> real OllamaEmbeddings initialized", m, OLLAMA_BASE_URL)
            return OllamaEmbeddings(model=m, base_url=OLLAMA_BASE_URL)
        except Exception as e:
            log.error("Ollama embedding service unreachable at %s (%s)", OLLAMA_BASE_URL, e)
            raise RuntimeError(
                f"Không thể kết nối tới dịch vụ Ollama tại {OLLAMA_BASE_URL} cho mô hình '{m}': {e}\n"
                f"Vui lòng kiểm tra Ollama đang chạy (`ollama serve`) và đã pull model (`ollama pull {m}`)."
            ) from e

    else:
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER='{p}'. Các provider được hỗ trợ: 'huggingface', 'sentence-transformers', 'openai', 'ollama'."
        )

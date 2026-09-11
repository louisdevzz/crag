"""Multi-Provider LLM & Embedding Factory for Legal CRAG Agent.

Provides pluggable access to:
- Groq (ultra-low latency LPU inference)
- OpenAI (GPT-4o, GPT-4o-mini)
- OpenRouter (DeepSeek V3/R1, Qwen 2.5 72B, Claude 3.5 Sonnet, etc.)
- Ollama (local on-premise execution)
"""
from __future__ import annotations

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from config import (
    EMBEDDING_MODEL,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
    OPENROUTER_BASE_URL,
)


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
    p = (provider or LLM_PROVIDER).lower().strip()
    m = model or LLM_MODEL
    t = LLM_TEMPERATURE if temperature is None else temperature

    try:
        if p == "groq":
            api_key = kwargs.pop("api_key", os.getenv("GROQ_API_KEY"))
            if not api_key:
                return None
            from langchain_groq import ChatGroq
            return ChatGroq(model=m, temperature=t, api_key=api_key, **kwargs)

        elif p == "openai":
            api_key = kwargs.pop("api_key", os.getenv("OPENAI_API_KEY"))
            if not api_key:
                return None
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=m, temperature=t, api_key=api_key, **kwargs)

        elif p == "openrouter":
            api_key = kwargs.pop("api_key", os.getenv("OPENROUTER_API_KEY"))
            if not api_key:
                return None
            from langchain_openai import ChatOpenAI
            base_url = kwargs.pop("base_url", OPENROUTER_BASE_URL)
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
            return ChatOllama(model=m, temperature=t, base_url=base_url, **kwargs)

        else:
            return None
    except Exception:
        return None

class FallbackDenseEmbeddings:
    """Deterministic lightweight dense embeddings (384-dim) for offline/local execution.

    Uses character n-grams and token hashing with L2-normalization to produce dense
    vectors with genuine lexical-semantic cosine properties without external services.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        import hashlib
        import math
        vec = [0.0] * self.dim
        tokens = text.lower().replace(",", " ").replace(".", " ").split()
        if not tokens:
            return vec
        for idx, t in enumerate(tokens):
            # Word hash
            h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
            dim_idx = h % self.dim
            weight = 1.0 / math.log2(idx + 2)
            vec[dim_idx] += weight
            # Character trigram hashes for subword sensitivity
            for i in range(max(0, len(t) - 2)):
                sub = t[i : i + 3]
                sub_h = int(hashlib.sha256(sub.encode("utf-8")).hexdigest(), 16)
                vec[sub_h % self.dim] += 0.5 * weight
        # L2-normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings(provider: Optional[str] = None, model: Optional[str] = None):
    """Factory function to initialize text embedding models."""
    p = (provider or os.getenv("EMBEDDING_PROVIDER", "ollama")).lower().strip()
    m = model or EMBEDDING_MODEL

    if p == "ollama":
        try:
            import requests
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1)
            if resp.status_code == 200:
                from langchain_ollama import OllamaEmbeddings
                return OllamaEmbeddings(model=m, base_url=OLLAMA_BASE_URL)
        except Exception:
            pass

    elif p in ("huggingface", "sentence-transformers"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            return HuggingFaceEmbeddings(model_name=m)
        except Exception:
            pass

    # Fallback to deterministic local vectorizer
    return FallbackDenseEmbeddings(dim=384)

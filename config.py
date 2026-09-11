"""Central Type-Safe Configuration System for Legal CRAG Assistant V3.

Inspired by Hermes Agent and OpenClaw schema-driven configuration principles.
Uses Pydantic BaseModels for rigorous validation, environment overrides,
and provides backward-compatible module-level exports.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for Model Providers and Endpoints."""
    provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq").lower().strip())
    model: str = Field(default="")
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    openrouter_base_url: str = Field(default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    default_models: Dict[str, str] = Field(
        default_factory=lambda: {
            "groq": "qwen/qwen3.8-27b",
            "openai": "gpt-4o-mini",
            "openrouter": "deepseek/deepseek-chat",
            "ollama": "qwen3.8:latest",
        }
    )

    def model_post_init(self, __context):
        if not self.model:
            self.model = os.getenv("LLM_MODEL", self.default_models.get(self.provider, "qwen/qwen3.8-27b"))


class RetrievalConfig(BaseModel):
    """Configuration for Vector Search, BM25, and Fusion."""
    embedding_provider: str = Field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "huggingface").lower().strip())
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    reranker_model: str = Field(default_factory=lambda: os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"))
    top_k_dense: int = Field(default_factory=lambda: int(os.getenv("TOP_K_DENSE", "20")))
    top_k_bm25: int = Field(default_factory=lambda: int(os.getenv("TOP_K_BM25", "20")))
    top_k_rerank: int = Field(default_factory=lambda: int(os.getenv("TOP_K_RERANK", "5")))
    rrf_k: int = Field(default_factory=lambda: int(os.getenv("RRF_K", "60")))


class CRAGConfig(BaseModel):
    """Calibrated Thresholds for 3-Branch Corrective RAG Routing."""
    t_low: float = Field(default_factory=lambda: float(os.getenv("T_LOW", "0.40")))
    t_high: float = Field(default_factory=lambda: float(os.getenv("T_HIGH", "0.80")))
    internal_strip_min: float = Field(default_factory=lambda: float(os.getenv("INTERNAL_STRIP_MIN", "0.40")))


class SecurityConfig(BaseModel):
    """Governance Rules, Official Domain Allow-List, and Memory Allow-List."""
    official_domains: Set[str] = Field(
        default_factory=lambda: {
            "vbpl.vn",
            "vanban.chinhphu.vn",
            "moj.gov.vn",
            "chinhphu.vn",
            "thuvienphapluat.vn",
            "congbao.chinhphu.vn",
        }
    )
    allowed_memory_keys: Set[str] = Field(
        default_factory=lambda: {
            "business_type",
            "industry",
            "province",
            "frequent_topic",
            "preferred_answer",
        }
    )


class PathConfig(BaseModel):
    """Directory Layout and File Paths."""
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "data")
    raw_data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "data" / "raw")
    processed_data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "data" / "processed")
    corpus_manifest_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "data" / "corpus_manifest.json")
    db_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "app.db")
    chroma_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "chroma")
    chroma_collection: str = "legal_corpus_v1"
    eval_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval")
    calibration_set_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval" / "calibration_set.json")
    test_set_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval" / "test_set.json")


class AppConfig(BaseModel):
    """Unified Application Configuration Singleton."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    crag: CRAGConfig = Field(default_factory=CRAGConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    paths: PathConfig = Field(default_factory=PathConfig)


# Global singleton instance
CONFIG = AppConfig()

# Backward-compatible module-level variable aliases
LLM_PROVIDER = CONFIG.llm.provider
LLM_MODEL = CONFIG.llm.model
LLM_TEMPERATURE = CONFIG.llm.temperature
DEFAULT_MODELS = CONFIG.llm.default_models
OLLAMA_BASE_URL = CONFIG.llm.ollama_base_url
OPENROUTER_BASE_URL = CONFIG.llm.openrouter_base_url

EMBEDDING_PROVIDER = CONFIG.retrieval.embedding_provider
EMBEDDING_MODEL = CONFIG.retrieval.embedding_model
RERANKER_MODEL = CONFIG.retrieval.reranker_model
TOP_K_DENSE = CONFIG.retrieval.top_k_dense
TOP_K_BM25 = CONFIG.retrieval.top_k_bm25
TOP_K_RERANK = CONFIG.retrieval.top_k_rerank
RRF_K = CONFIG.retrieval.rrf_k

T_LOW = CONFIG.crag.t_low
T_HIGH = CONFIG.crag.t_high
INTERNAL_STRIP_MIN = CONFIG.crag.internal_strip_min

OFFICIAL_DOMAINS = CONFIG.security.official_domains
ALLOWED_MEMORY_KEYS = CONFIG.security.allowed_memory_keys

BASE_DIR = CONFIG.paths.base_dir
DATA_DIR = CONFIG.paths.data_dir
RAW_DATA_DIR = CONFIG.paths.raw_data_dir
PROCESSED_DATA_DIR = CONFIG.paths.processed_data_dir
CORPUS_MANIFEST_PATH = CONFIG.paths.corpus_manifest_path
DB_PATH = CONFIG.paths.db_path
CHROMA_DIR = CONFIG.paths.chroma_dir
CHROMA_COLLECTION = CONFIG.paths.chroma_collection
EVAL_DIR = CONFIG.paths.eval_dir
CALIBRATION_SET_PATH = CONFIG.paths.calibration_set_path
TEST_SET_PATH = CONFIG.paths.test_set_path

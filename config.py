"""Central type-safe configuration system for the Legal CRAG assistant."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root with override enabled.
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


class LLMConfig(BaseModel):
    """Configuration for Model Providers and Endpoints."""
    provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq").lower().strip())
    model: str = Field(default="")
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.3")))
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
    # Provider fallback order when primary provider is unavailable.
    fallback_providers: List[str] = Field(
        default_factory=lambda: [
            p.strip().lower()
            for p in os.getenv("LLM_FALLBACK_PROVIDERS", "groq,openrouter,ollama").split(",")
            if p.strip()
        ]
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

class SessionConfig(BaseModel):
    """Chat Runtime: short-term conversational memory window."""
    history_turns: int = Field(default_factory=lambda: int(os.getenv("HISTORY_TURNS", "4")))


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


def _resolve_crag_home() -> Path:
    raw = os.getenv("CRAG_HOME", "~/.crag")
    return Path(raw).expanduser().resolve()


def _resolve_db_path(crag_home: Path) -> Path:
    raw = os.getenv("DB_PATH") or os.getenv("CRAG_DB_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "app.db").resolve()


def _resolve_chroma_dir(crag_home: Path) -> Path:
    raw = os.getenv("CHROMA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "chroma").resolve()


def _resolve_data_dir(crag_home: Path) -> Path:
    raw = os.getenv("DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "data").resolve()


def _resolve_raw_data_dir(crag_home: Path) -> Path:
    raw = os.getenv("RAW_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "data" / "raw").resolve()


def _resolve_processed_data_dir(crag_home: Path) -> Path:
    raw = os.getenv("PROCESSED_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "data" / "processed").resolve()


def _resolve_corpus_manifest_path(crag_home: Path) -> Path:
    raw = os.getenv("CORPUS_MANIFEST_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "data" / "corpus_manifest.json").resolve()


def _resolve_upload_dir(crag_home: Path) -> Path:
    raw = os.getenv("UPLOAD_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (crag_home / "data" / "uploads").resolve()


class PathConfig(BaseModel):
    """Directory Layout and File Paths."""
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    crag_home: Path = Field(default_factory=_resolve_crag_home)
    data_dir: Path = Field(default_factory=lambda: _resolve_data_dir(_resolve_crag_home()))
    raw_data_dir: Path = Field(default_factory=lambda: _resolve_raw_data_dir(_resolve_crag_home()))
    processed_data_dir: Path = Field(default_factory=lambda: _resolve_processed_data_dir(_resolve_crag_home()))
    corpus_manifest_path: Path = Field(default_factory=lambda: _resolve_corpus_manifest_path(_resolve_crag_home()))
    db_path: Path = Field(default_factory=lambda: _resolve_db_path(_resolve_crag_home()))
    chroma_dir: Path = Field(default_factory=lambda: _resolve_chroma_dir(_resolve_crag_home()))
    chroma_collection: str = Field(default_factory=lambda: os.getenv("CHROMA_COLLECTION", "legal_corpus_v1"))
    eval_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval")
    calibration_set_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval" / "calibration_set.json")
    test_set_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "eval" / "test_set.json")
    upload_dir: Path = Field(default_factory=lambda: _resolve_upload_dir(_resolve_crag_home()))

class AppConfig(BaseModel):
    """Unified Application Configuration Singleton."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    crag: CRAGConfig = Field(default_factory=CRAGConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
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
CRAG_HOME = CONFIG.paths.crag_home
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
UPLOAD_DIR = CONFIG.paths.upload_dir

HISTORY_TURNS = CONFIG.session.history_turns
LLM_FALLBACK_PROVIDERS = CONFIG.llm.fallback_providers

"""Central Configuration Module for Legal CRAG Assistant V3."""
from __future__ import annotations

import os
from pathlib import Path

# ==============================================================================
# LLM PROVIDER & MODEL CONFIGURATION
# ==============================================================================
# Supported providers: "groq" | "openai" | "openrouter" | "ollama"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()

# Recommended default models per provider
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",         # Ultra-fast inference (<1s/turn)
    "openai": "gpt-4o-mini",                   # High quality & cost-effective
    "openrouter": "deepseek/deepseek-chat",     # Unified gateway for DeepSeek / Qwen
    "ollama": "qwen2.5:14b-instruct",          # Local air-gapped execution
}

LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODELS.get(LLM_PROVIDER, "llama-3.3-70b-versatile"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Provider endpoints (optional overrides)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# ==============================================================================
# EMBEDDING & RERANKER
# ==============================================================================
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface").lower().strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Fallback lightweight model when GPU/memory is constrained
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ==============================================================================
# RETRIEVAL & CRAG THRESHOLDS (Calibration-Optimized)
# ==============================================================================
TOP_K_DENSE = int(os.getenv("TOP_K_DENSE", "20"))
TOP_K_BM25 = int(os.getenv("TOP_K_BM25", "20"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))

# Two Independent Relevance Thresholds for 3-Branch CRAG
T_LOW = float(os.getenv("T_LOW", "0.35"))
T_HIGH = float(os.getenv("T_HIGH", "0.70"))
INTERNAL_STRIP_MIN = float(os.getenv("INTERNAL_STRIP_MIN", "0.40"))
RRF_K = int(os.getenv("RRF_K", "60"))

# ==============================================================================
# CONTROLLED WEB SEARCH & ALLOW-LIST
# ==============================================================================
OFFICIAL_DOMAINS = {
    "vbpl.vn",
    "vanban.chinhphu.vn",
    "moj.gov.vn",
    "chinhphu.vn",
    "thuvienphapluat.vn",
    "congbao.chinhphu.vn",
}

# ==============================================================================
# SEMANTIC MEMORY ALLOW-LIST (Privacy & Anti-Contamination Guardrail)
# ==============================================================================
ALLOWED_MEMORY_KEYS = {
    "business_type",      # e.g., Cong ty TNHH, Cong ty Co phan, Doanh nghiep tu nhan
    "industry",           # e.g., Xay dung, Thuong mai dien tu, Ban le, Cong nghe thong tin
    "province",           # e.g., Ha Noi, TP.HCM, Long An, Da Nang
    "frequent_topic",     # e.g., Lao dong, Hop dong, Doan phi, Dang ky kinh doanh
    "preferred_answer",   # e.g., Ngan gon, Chi tiet, Trich dan day du
}

# ==============================================================================
# DIRECTORY PATHS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CORPUS_MANIFEST_PATH = DATA_DIR / "corpus_manifest.json"

DB_PATH = BASE_DIR / "app.db"
CHROMA_DIR = BASE_DIR / "chroma"
CHROMA_COLLECTION = "legal_corpus_v1"
EVAL_DIR = BASE_DIR / "eval"
CALIBRATION_SET_PATH = EVAL_DIR / "calibration_set.json"
TEST_SET_PATH = EVAL_DIR / "test_set.json"

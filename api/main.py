"""FastAPI RESTful Gateway for Legal CRAG Assistant (Layer 1)."""
from __future__ import annotations

import json as jsonlib
import os
import pickle
import sqlite3
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import get_crag_app
from agent.streaming import AnswerFieldExtractor, NODE_STAGE
from config import CHROMA_DIR, CONFIG, DB_PATH, PROCESSED_DATA_DIR, RAW_DATA_DIR
from ingest import add_document_to_indexes, delete_document_from_indexes, get_vectorstore
from legal.preprocessor import UniversalLegalPreprocessor
from logging_config import get_logger
from memory.extractor import extract_and_save_memories
from memory.store import get_memory_store
from monitoring import trace_config

log = get_logger(__name__)


app = FastAPI(
    title="Legal CRAG Assistant API Gateway",
    description="RESTful API for Vietnamese Corporate & Labor Law Corrective RAG Agent",
    version="1.0.0",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User legal query")
    client_id: Optional[str] = Field(None, description="Anonymous client identifier from localStorage")
    session_id: Optional[str] = Field(None, description="Session identifier for multi-turn thread")
    as_of_date: Optional[str] = Field(None, description="Reference date for temporal validity (YYYY-MM-DD)")


class ClaimItem(BaseModel):
    text: str
    source_ids: List[str] = []


class GenerationOutput(BaseModel):
    answer: str
    claims: List[ClaimItem] = []
    abstain: bool = False


class CitationReport(BaseModel):
    ok: bool
    errors: List[str] = []
    valid_citations: List[str] = []
    citation_accuracy: float = 1.0
    citation_coverage: float = 1.0


class ChatResponse(BaseModel):
    client_id: str
    session_id: str
    query: str
    route: str
    crag_action: str
    generation: GenerationOutput
    citation_report: CitationReport
    evidence_count: int
    evidence: List[Dict[str, Any]] = []


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "legal-crag-assistant", "version": "3.0.0"}


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """Execute Legal CRAG Agent turn."""
    log.info("=== [TURN START] (non-streaming) query=%r client_id=%s ===", req.query[:100], req.client_id)
    store = get_memory_store()

    # 1. Resolve client and session
    client_record = store.get_or_create_client(req.client_id)
    client_id = client_record["id"]
    session_id = store.create_session(client_id, req.session_id)

    # 2. Extract semantic memory attributes if present
    extract_and_save_memories(client_id, req.query)

    # 3. Retrieve formatted non-legal memory context for entity resolution
    memory_context = store.format_memory_context(client_id)

    # 4. Invoke LangGraph
    graph_app = get_crag_app()
    state_input = {
        "client_id": client_id,
        "session_id": session_id,
        "query": req.query,
        "as_of_date": req.as_of_date,
        "memory_context": memory_context,
    }

    config = trace_config(thread_id=session_id, client_id=client_id)
    try:
        res = graph_app.invoke(state_input, config=config)
    except Exception as e:
        log.error("=== [TURN FAILED] error=%s ===", e)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

    route = res.get("route", "rag")
    action = res.get("crag_action", "DATABASE" if route == "database" else "CORRECT")
    generation = res.get("generation", {})
    citation_report = res.get("citation_report", {})
    evidence = res.get("evidence", [])

    # 5. Log episodic turn to database
    answer_text = generation.get("answer", "")
    store.log_query(
        client_id=client_id,
        session_id=session_id,
        question=req.query,
        answer=answer_text,
        route=route,
        crag_action=action,
        source_type=evidence[0].get("retrieval_source", "internal") if evidence else "none",
    )
    log.info("=== [TURN DONE] route=%s crag_action=%s evidence=%d answer_chars=%d ===", route, action, len(evidence), len(answer_text))

    return ChatResponse(
        client_id=client_id,
        session_id=session_id,
        query=req.query,
        route=route,
        crag_action=action,
        generation=GenerationOutput(
            answer=answer_text,
            claims=[ClaimItem(**c) for c in generation.get("claims", [])],
            abstain=generation.get("abstain", False),
        ),
        citation_report=CitationReport(
            ok=citation_report.get("ok", True),
            errors=citation_report.get("errors", []),
            valid_citations=citation_report.get("valid_citations", []),
            citation_accuracy=citation_report.get("citation_accuracy", 1.0),
            citation_coverage=citation_report.get("citation_coverage", 1.0),
        ),
        evidence_count=len(evidence),
        evidence=evidence[:6],  # Return top 6 for UI display
    )


def _sse(event: Dict[str, Any]) -> str:
    return f"data: {jsonlib.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest) -> StreamingResponse:
    """Execute Legal CRAG Agent turn with live SSE streaming.

    Emits, in order:
    - `{"type": "node", "node": ..., "stage": 0-3}` as each LangGraph node
      actually completes (real pipeline progress, not a client-side timer).
    - `{"type": "token", "text": ...}` deltas of the generated answer text,
      decoded live from the `generate` node's structured JSON output via
      `AnswerFieldExtractor` (deterministic routes like `database` emit no
      token events — their answer arrives whole in the final `done` event).
    - `{"type": "done", "payload": {...}}` once with the same shape as
      `POST /api/chat`'s response body.
    - `{"type": "error", "message": ...}` if the agent run raises.
    """
    log.info("=== [TURN START] (streaming) query=%r client_id=%s ===", req.query[:100], req.client_id)
    store = get_memory_store()

    client_record = store.get_or_create_client(req.client_id)
    client_id = client_record["id"]
    session_id = store.create_session(client_id, req.session_id)

    extract_and_save_memories(client_id, req.query)
    memory_context = store.format_memory_context(client_id)

    graph_app = get_crag_app()
    state_input = {
        "client_id": client_id,
        "session_id": session_id,
        "query": req.query,
        "as_of_date": req.as_of_date,
        "memory_context": memory_context,
    }
    config = trace_config(thread_id=session_id, client_id=client_id)

    async def event_stream() -> AsyncIterator[str]:
        final_state: Dict[str, Any] = dict(state_input)
        extractor = AnswerFieldExtractor()
        seen_nodes = set()
        try:
            async for mode, chunk in graph_app.astream(
                state_input, config=config, stream_mode=["updates", "custom"]
            ):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        if update:
                            final_state.update(update)
                        if node_name not in seen_nodes:
                            seen_nodes.add(node_name)
                            log.info("[SSE] node=%s stage=%d", node_name, NODE_STAGE.get(node_name, 3))
                            yield _sse({
                                "type": "node",
                                "node": node_name,
                                "stage": NODE_STAGE.get(node_name, 3),
                            })
                elif mode == "custom":
                    piece = chunk.get("raw_chunk", "") if isinstance(chunk, dict) else ""
                    if not piece:
                        continue
                    delta = extractor.feed(piece)
                    if delta:
                        yield _sse({"type": "token", "text": delta})
        except Exception as e:
            log.error("=== [TURN FAILED] (streaming) error=%s ===", e)
            yield _sse({"type": "error", "message": f"Agent execution failed: {e}"})
            return

        route = final_state.get("route", "rag")
        action = final_state.get("crag_action", "DATABASE" if route == "database" else "CORRECT")
        generation = final_state.get("generation", {})
        citation_report = final_state.get("citation_report", {})
        evidence = final_state.get("evidence", [])
        answer_text = generation.get("answer", "")

        store.log_query(
            client_id=client_id,
            session_id=session_id,
            question=req.query,
            answer=answer_text,
            route=route,
            crag_action=action,
            source_type=evidence[0].get("retrieval_source", "internal") if evidence else "none",
        )
        log.info("=== [TURN DONE] (streaming) route=%s crag_action=%s evidence=%d answer_chars=%d ===", route, action, len(evidence), len(answer_text))

        payload = {
            "client_id": client_id,
            "session_id": session_id,
            "query": req.query,
            "route": route,
            "crag_action": action,
            "generation": {
                "answer": answer_text,
                "claims": generation.get("claims", []),
                "abstain": generation.get("abstain", False),
            },
            "citation_report": {
                "ok": citation_report.get("ok", True),
                "errors": citation_report.get("errors", []),
                "valid_citations": citation_report.get("valid_citations", []),
                "citation_accuracy": citation_report.get("citation_accuracy", 1.0),
                "citation_coverage": citation_report.get("citation_coverage", 1.0),
            },
            "evidence_count": len(evidence),
            "evidence": evidence[:6],
        }
        yield _sse({"type": "done", "payload": payload})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/history/{client_id}")
def get_history(client_id: str, session_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve episodic conversation history for a client, optionally scoped to one session."""
    store = get_memory_store()
    return store.get_query_history(client_id, session_id=session_id, limit=limit)


@app.get("/api/memory/{client_id}")
def get_client_memory(client_id: str) -> Dict[str, Any]:
    """Retrieve semantic profile memories for a client."""
    store = get_memory_store()
    memories = store.get_client_memories(client_id)
    return {
        "client_id": client_id,
        "memories": memories,
        "formatted_context": store.format_memory_context(client_id),
    }


@app.delete("/api/memory/{client_id}")
def clear_memory(client_id: str) -> Dict[str, Any]:
    """Clear all semantic memory for a client."""
    store = get_memory_store()
    deleted = store.clear_client_memories(client_id)
    return {"client_id": client_id, "cleared_count": deleted}


@app.get("/api/documents")
def list_documents() -> List[Dict[str, Any]]:
    """List indexed legal documents from database."""
    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, document_number, title, document_type, issuing_authority,
                   effective_from, status, source_url
            FROM legal_documents
            ORDER BY id
            """
        )
        return [dict(r) for r in cur.fetchall()]


# ==============================================================================
# ADMIN DATA CONSOLE — Corpus & Vector Store Ingestion Management (Layer 1)
# ==============================================================================
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


class AdminDocumentSummary(BaseModel):
    id: str
    document_number: str
    title: str
    document_type: Optional[str] = None
    issuing_authority: Optional[str] = None
    issued_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    status: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    provisions_count: int = 0


class AdminStats(BaseModel):
    total_documents: int
    total_provisions: int
    bm25_indexed: int
    chroma_indexed: int


class IngestResult(BaseModel):
    document_id: str
    document_number: str
    title: str
    provisions_count: int
    strips_count: int
    corpus_total_provisions: int


class DeleteResult(BaseModel):
    document_id: str
    document_number: str
    deleted_provisions: int
    corpus_total_provisions: int


@app.get("/api/admin/documents", response_model=List[AdminDocumentSummary])
def admin_list_documents() -> List[Dict[str, Any]]:
    """List every indexed legal document with its provision count for the Admin console."""
    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT d.*, COUNT(p.id) AS provisions_count
            FROM legal_documents d
            LEFT JOIN provisions p ON p.document_id = d.id
            GROUP BY d.id
            ORDER BY d.retrieved_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]


@app.get("/api/admin/stats", response_model=AdminStats)
def admin_stats() -> Dict[str, Any]:
    """Report corpus ingestion coverage across SQLite, the BM25 index, and Chroma."""
    with sqlite3.connect(str(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM legal_documents")
        total_documents = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM provisions")
        total_provisions = cur.fetchone()[0]

    bm25_indexed = 0
    bm25_path = PROCESSED_DATA_DIR / "bm25_index.pkl"
    if bm25_path.exists():
        with open(bm25_path, "rb") as f:
            bm25_indexed = pickle.load(f).get("count", 0)

    chroma_indexed = 0
    try:
        chroma_indexed = get_vectorstore(CHROMA_DIR)._collection.count()
    except Exception:
        chroma_indexed = 0

    return {
        "total_documents": total_documents,
        "total_provisions": total_provisions,
        "bm25_indexed": bm25_indexed,
        "chroma_indexed": chroma_indexed,
    }


@app.post("/api/admin/documents/upload", response_model=IngestResult)
async def admin_upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a legal document file; preprocess and ingest it into SQLite, BM25, and Chroma."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = RAW_DATA_DIR / file.filename
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    dest_path.write_bytes(content)

    try:
        preprocessor = UniversalLegalPreprocessor(enable_vision_ocr=False)
        result = preprocessor.process_file(dest_path)
        ingest_result = add_document_to_indexes(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e

    return ingest_result


@app.delete("/api/admin/documents/{document_id}", response_model=DeleteResult)
def admin_delete_document(document_id: str) -> Dict[str, Any]:
    """Remove a document and its provisions from SQLite, BM25, and Chroma."""
    try:
        return delete_document_from_indexes(document_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ==============================================================================
# ADMIN SETTINGS — General Info & Live LLM Provider/Model Switching
# ==============================================================================
PROVIDER_LABELS: Dict[str, str] = {
    "groq": "Groq",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}

# Curated, known-valid model IDs offered per provider when the provider has no
# live model-listing API (only Groq does, via providers/groq_models.py).
STATIC_PROVIDER_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "openrouter": [
        "deepseek/deepseek-chat",
        "qwen/qwen-2.5-72b-instruct",
        "anthropic/claude-3.5-sonnet",
        "meta-llama/llama-3.3-70b-instruct",
    ],
    "ollama": ["qwen3.8:latest", "qwen2.5:14b-instruct"],
}


class ModelSettings(BaseModel):
    provider: str
    model: str
    temperature: float


class ProviderOption(BaseModel):
    provider: str
    label: str
    default_model: str
    available_models: List[str]
    configured: bool


class AdminSettings(BaseModel):
    version: str
    architecture: str
    fastapi_gateway: str
    embedding_model: str
    reranker_model: str
    t_low: float
    t_high: float
    current: ModelSettings
    providers: List[ProviderOption]


class UpdateModelRequest(BaseModel):
    provider: str = Field(..., description="One of: groq, openai, openrouter, ollama")
    model: str = Field(..., min_length=1)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


def _provider_is_configured(provider: str) -> bool:
    if provider == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY"))
    if provider == "ollama":
        return True  # Local runtime; no API key required.
    return False


def _provider_options() -> List[Dict[str, Any]]:
    options = []
    for provider, label in PROVIDER_LABELS.items():
        if provider == "groq":
            from providers.groq_models import list_groq_free_models

            models = list_groq_free_models(api_key=os.getenv("GROQ_API_KEY")) or [
                CONFIG.llm.default_models.get("groq", "qwen/qwen3.8-27b")
            ]
        else:
            models = STATIC_PROVIDER_MODELS.get(provider, [])

        options.append(
            {
                "provider": provider,
                "label": label,
                "default_model": CONFIG.llm.default_models.get(provider, ""),
                "available_models": models,
                "configured": _provider_is_configured(provider),
            }
        )
    return options


@app.get("/api/admin/settings", response_model=AdminSettings)
def admin_get_settings() -> Dict[str, Any]:
    """Report general app info and the live-editable LLM provider/model configuration."""
    return {
        "version": "3.0.0",
        "architecture": "LangGraph + Ollama/Groq + Chroma + BM25",
        "fastapi_gateway": "http://localhost:8000",
        "embedding_model": CONFIG.retrieval.embedding_model,
        "reranker_model": CONFIG.retrieval.reranker_model,
        "t_low": CONFIG.crag.t_low,
        "t_high": CONFIG.crag.t_high,
        "current": {
            "provider": CONFIG.llm.provider,
            "model": CONFIG.llm.model,
            "temperature": CONFIG.llm.temperature,
        },
        "providers": _provider_options(),
    }


@app.patch("/api/admin/settings/model", response_model=ModelSettings)
def admin_update_model(req: UpdateModelRequest) -> Dict[str, Any]:
    """Switch the active LLM provider/model at runtime (no server restart required)."""
    provider = req.provider.lower().strip()
    if provider not in PROVIDER_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. Allowed: {sorted(PROVIDER_LABELS)}",
        )

    CONFIG.llm.provider = provider
    CONFIG.llm.model = req.model.strip()
    if req.temperature is not None:
        CONFIG.llm.temperature = req.temperature

    return {
        "provider": CONFIG.llm.provider,
        "model": CONFIG.llm.model,
        "temperature": CONFIG.llm.temperature,
    }


# Mount Web UI (Inspired by DeepSeek Harness / Hermes Agent)
from fastapi.staticfiles import StaticFiles

frontend_out = Path(__file__).resolve().parent.parent / "frontend" / "out"
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
target_dir = frontend_out if frontend_out.exists() else frontend_dir
if target_dir.exists():
    app.mount("/", StaticFiles(directory=str(target_dir), html=True), name="frontend")

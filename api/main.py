"""FastAPI RESTful Gateway for Legal CRAG Assistant (Layer 1)."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json as jsonlib
import os
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
from agent.nodes import derive_route_and_action
from agent.runtime import persist_turn, prepare_turn
from agent.streaming import chunk_text_for_pseudo_stream, node_stage
from config import CONFIG, DB_PATH, UPLOAD_DIR
from ingestion import documents as documents_repo
from ingestion import chunks as chunks_repo
from ingestion import indexer
from ingestion import jobs as jobs_repo
from ingestion.worker import submit_ingestion
from logging_config import get_logger
from memory.store import get_memory_store
from monitoring import trace_config

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler: ensure system directories/database exist, then warm the
    embedding model, reranker, and Chroma vectorstore singletons (retrieval.dense,
    retrieval.reranker, llm.get_embeddings) once at boot — each is expensive to
    construct (loads a transformer model from disk) but cached for the life of the
    process, so paying that cost here means every `crag_search` call and document
    upload afterward is fast instead of the first one after each cold start."""
    try:
        from scripts.init_system import init_system
        init_system(quiet=True)
        log.info("System initialized successfully on startup (DB at %s)", DB_PATH)
    except Exception as e:
        log.warning("Auto-initialization on startup encountered warning: %s", e)

    try:
        import asyncio
        await asyncio.to_thread(_warm_retrieval_singletons)
    except Exception as e:
        log.warning("Retrieval model warmup failed (%s) -> will lazy-load on first request", e)

    yield


def _warm_retrieval_singletons() -> None:
    from retrieval.dense import get_vectorstore
    from retrieval.reranker import get_reranker

    get_vectorstore()
    get_reranker()
    log.info("Retrieval singletons warmed (embedding model + reranker + Chroma vectorstore ready)")


app = FastAPI(
    title="Legal CRAG Assistant API Gateway",
    description="RESTful API for Vietnamese Corporate & Labor Law Corrective RAG Agent",
    version="1.0.0",
    lifespan=lifespan,
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

    # 1-3. Resolve client/session, extract semantic memory, assemble Context Manager input.
    client_id, session_id, state_input = prepare_turn(req.client_id, req.session_id, req.query, req.as_of_date)

    # 4. Invoke the Agent Core (LangGraph).
    graph_app = get_crag_app()
    config = trace_config(thread_id=session_id, client_id=client_id)
    try:
        res = graph_app.invoke(state_input, config=config)
    except Exception as e:
        log.error("=== [TURN FAILED] error=%s ===", e)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

    route = res.get("route", "rag")
    action = res.get("crag_action", "CORRECT")
    generation = res.get("generation", {})
    citation_report = res.get("citation_report", {})
    evidence = res.get("evidence", [])
    answer_text = generation.get("answer", "")

    # 5. Persist the turn (Context Manager's write side).
    persist_turn(
        client_id, session_id, req.query, answer_text,
        route=route, crag_action=action,
        source_type=evidence[0].get("retrieval_source", "internal") if evidence else "none",
        evidence=evidence,
        citation_report=citation_report,
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

    client_id, session_id, state_input = prepare_turn(req.client_id, req.session_id, req.query, req.as_of_date)
    graph_app = get_crag_app()
    config = trace_config(thread_id=session_id, client_id=client_id)

    async def event_stream() -> AsyncIterator[str]:
        # Manual reducer accumulation: `stream_mode="updates"` yields each node's raw
        # partial-update dict, not the graph's already-merged state (that view only exists
        # via "values" mode or a final `.invoke()` return) — so `evidence`/`tool_trace`
        # (both `operator.add` reducers on AgentState) must be accumulated here the same way
        # LangGraph would internally, and `generation`/`citation_report` simply overwrite.
        evidence: List[Dict[str, Any]] = []
        tool_trace: List[Dict[str, Any]] = []
        generation: Dict[str, Any] = {}
        citation_report: Dict[str, Any] = {}
        agent_call_index = 0
        answer_streamed = False

        try:
            async for mode, chunk in graph_app.astream(
                state_input, config=config, stream_mode=["updates", "custom"]
            ):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        if not update:
                            continue
                        if "evidence" in update:
                            evidence.extend(update["evidence"])
                        if "tool_trace" in update:
                            tool_trace.extend(update["tool_trace"])
                        if "generation" in update:
                            generation = update["generation"]
                        if "citation_report" in update:
                            citation_report = update["citation_report"]

                        stage = node_stage(node_name, agent_call_index)
                        if node_name == "agent":
                            agent_call_index += 1
                        if stage is not None:
                            log.info("[SSE] node=%s stage=%d", node_name, stage)
                            yield _sse({"type": "node", "node": node_name, "stage": stage})
                elif mode == "custom":
                    if not isinstance(chunk, dict):
                        continue
                    if "tool_start" in chunk:
                        yield _sse({"type": "tool_start", **chunk["tool_start"]})
                    elif "tool_end" in chunk:
                        yield _sse({"type": "tool_end", **chunk["tool_end"]})
                    elif "final_answer" in chunk and not answer_streamed:
                        answer_streamed = True
                        for piece in chunk_text_for_pseudo_stream(chunk["final_answer"]):
                            yield _sse({"type": "token", "text": piece})
        except Exception as e:
            log.error("=== [TURN FAILED] (streaming) error=%s ===", e)
            yield _sse({"type": "error", "message": f"Agent execution failed: {e}"})
            return

        route, action = derive_route_and_action(tool_trace)
        answer_text = generation.get("answer", "")

        persist_turn(
            client_id, session_id, req.query, answer_text,
            route=route, crag_action=action,
            source_type=evidence[0].get("retrieval_source", "internal") if evidence else "none",
            evidence=evidence,
            citation_report=citation_report,
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
    """List documents currently visible to CRAG retrieval (status = READY)."""
    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, document_number, title, document_type, issuing_authority,
                   effective_from, status, source_url
            FROM documents
            WHERE status = 'READY'
            ORDER BY id
            """
        )
        return [dict(r) for r in cur.fetchall()]


# ==============================================================================
# ADMIN DATA CONSOLE — Document Ingestion Pipeline Management (Layer 1)
# ==============================================================================
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


class AdminDocumentSummary(BaseModel):
    id: str
    filename: str
    document_number: Optional[str] = None
    title: str
    document_type: Optional[str] = None
    issuing_authority: Optional[str] = None
    issued_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    status: str
    page_count: int = 0
    chunk_count: int = 0
    stage: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IngestionJobInfo(BaseModel):
    id: str
    stage: str
    progress: float
    error_message: Optional[str] = None


class AdminDocumentDetail(AdminDocumentSummary):
    job: Optional[IngestionJobInfo] = None


class ChunkItem(BaseModel):
    id: str
    chunk_index: int
    chapter: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    heading: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    content: str
    token_count: Optional[int] = None


class AdminStats(BaseModel):
    total_documents: int
    ready: int
    processing: int
    failed: int


class UploadResult(BaseModel):
    document_id: str
    status: str
    job_id: str


class DeleteResult(BaseModel):
    document_id: str
    filename: str
    deleted_chunks: int


def _with_stage(doc: Dict[str, Any]) -> Dict[str, Any]:
    job = jobs_repo.get_job_for_document(doc["id"])
    doc = dict(doc)
    doc["stage"] = job["stage"] if job and doc["status"] == "PROCESSING" else None
    return doc


@app.get("/api/admin/documents", response_model=List[AdminDocumentSummary])
def admin_list_documents() -> List[Dict[str, Any]]:
    """List every document in the corpus with its live ingestion status for the Admin console."""
    return [_with_stage(d) for d in documents_repo.list_documents()]


@app.get("/api/admin/documents/{document_id}", response_model=AdminDocumentDetail)
def admin_document_detail(document_id: str) -> Dict[str, Any]:
    """Document metadata plus its latest ingestion job (for the processing checklist)."""
    doc = documents_repo.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    job = jobs_repo.get_job_for_document(document_id)
    result = dict(doc)
    result["stage"] = job["stage"] if job and doc["status"] == "PROCESSING" else None
    result["job"] = job
    return result


@app.get("/api/admin/documents/{document_id}/chunks", response_model=List[ChunkItem])
def admin_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """Chunk browser for one document (Admin's window into what was actually indexed)."""
    if documents_repo.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return chunks_repo.list_chunks(document_id)


@app.get("/api/admin/stats", response_model=AdminStats)
def admin_stats() -> Dict[str, Any]:
    """Report corpus ingestion coverage without exposing embedding/index internals."""
    docs = documents_repo.list_documents()
    return {
        "total_documents": len(docs),
        "ready": sum(1 for d in docs if d["status"] == "READY"),
        "processing": sum(1 for d in docs if d["status"] in ("UPLOADED", "PROCESSING")),
        "failed": sum(1 for d in docs if d["status"] == "FAILED"),
    }


def _delete_document_fully(document_id: str) -> Dict[str, Any]:
    """Cascade-delete a document: SQLite row (+ its chunks/jobs via FK), its Chroma
    vectors, and rebuild the BM25 index so it never lingers in either index."""
    indexer.remove_document_from_chroma(document_id)
    doc = documents_repo.delete_document(document_id)
    corpus_total = indexer.rebuild_bm25_index()
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "deleted_chunks": doc.get("chunk_count", 0),
        "corpus_total_chunks": corpus_total,
    }


@app.post("/api/admin/documents/upload", response_model=UploadResult)
async def admin_upload_document(file: UploadFile = File(...), replace: bool = False) -> Dict[str, Any]:
    """Upload a legal document; ingestion runs asynchronously on a background worker
    (see `ingestion.pipeline`). Poll `GET /api/admin/documents/{id}` for live progress."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    content_hash = hashlib.sha256(content).hexdigest()

    existing = documents_repo.find_by_content_hash(content_hash)
    if existing and existing["status"] != "FAILED" and not replace:
        raise HTTPException(
            status_code=409,
            detail=f"File này đã tồn tại: '{existing['filename']}' (status={existing['status']}). "
                   f"Gửi lại với replace=true để thay thế.",
        )
    if existing:
        _delete_document_fully(existing["id"])

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = documents_repo.new_document_id()
    dest_path = UPLOAD_DIR / f"{doc_id}{ext}"
    dest_path.write_bytes(content)

    doc = documents_repo.create_document(
        filename=file.filename,
        file_path=str(dest_path),
        file_type=ext,
        content_hash=content_hash,
        document_id=doc_id,
    )
    job = jobs_repo.create_job(doc["id"])
    submit_ingestion(doc["id"])

    return {"document_id": doc["id"], "status": doc["status"], "job_id": job["id"]}


@app.delete("/api/admin/documents/{document_id}", response_model=DeleteResult)
def admin_delete_document(document_id: str) -> Dict[str, Any]:
    """Remove a document and its chunks from SQLite, BM25, and Chroma."""
    try:
        return _delete_document_fully(document_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0] if e.args else str(e)) from e


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

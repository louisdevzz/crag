"""FastAPI RESTful Gateway for Legal CRAG Assistant V3 (Layer 1)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import get_crag_app
from config import DB_PATH
from memory.extractor import extract_and_save_memories
from memory.store import get_memory_store


app = FastAPI(
    title="Legal CRAG Assistant V3 API Gateway",
    description="RESTful API for Vietnamese Corporate & Labor Law Corrective RAG Agent",
    version="3.0.0",
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

    config = {"configurable": {"thread_id": session_id}}
    try:
        res = graph_app.invoke(state_input, config=config)
    except Exception as e:
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


@app.get("/api/history/{client_id}")
def get_history(client_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve episodic conversation history for a client."""
    store = get_memory_store()
    return store.get_query_history(client_id, limit=limit)


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
                   effective_from, status
            FROM legal_documents
            ORDER BY id
            """
        )
        return [dict(r) for r in cur.fetchall()]


# Mount Web UI (Inspired by DeepSeek Harness / Hermes Agent)
from fastapi.staticfiles import StaticFiles

frontend_out = Path(__file__).resolve().parent.parent / "frontend" / "out"
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
target_dir = frontend_out if frontend_out.exists() else frontend_dir
if target_dir.exists():
    app.mount("/", StaticFiles(directory=str(target_dir), html=True), name="frontend")

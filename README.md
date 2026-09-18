# Legal CRAG Assistant

> AI Agent hỗ trợ tra cứu và tư vấn tuân thủ pháp luật doanh nghiệp Việt Nam, kết hợp **Agentic CRAG**, Hybrid Retrieval, Web Search có kiểm soát, Citation Validation, Session History và Long-term Memory.

<p>
  <img alt="Python 3.13" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js 14" src="https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-Agentic%20Workflow-1C3C3C">
  <img alt="pnpm 11.18.0" src="https://img.shields.io/badge/pnpm-11.18.0-F69220?logo=pnpm&logoColor=white">
</p>

## Overview

Legal CRAG Assistant được xây dựng theo kiến trúc **ReAct Agent + Corrective RAG (CRAG)**.

Không có Router phân loại câu hỏi trước khi vào Agent. Thay vào đó, LLM tự quyết định khi nào cần:

- tra cứu Knowledge Base nội bộ bằng `crag_search`;
- tìm kiếm nguồn pháp luật ngoài hệ thống bằng `controlled_web_search`;
- hoặc trả lời trực tiếp khi không cần tool.

Các câu trả lời pháp lý được kiểm tra lại bằng **Deterministic Citation Validator** trước khi trả về cho người dùng.

![Legal CRAG Workflow](docs/images/workflow.png)

## Key Features

- **Agentic ReAct Loop** với LangGraph: `agent ⇄ tools`.
- **Corrective RAG 3 trạng thái**: `CORRECT`, `AMBIGUOUS`, `INCORRECT`.
- **Hybrid Retrieval**: Dense Retrieval với Chroma + Lexical Retrieval với BM25.
- **Reciprocal Rank Fusion (RRF)** và Cross-Encoder Reranking.
- **Controlled Web Search** giới hạn nguồn pháp luật theo allow-list.
- **Citation Validation** kiểm tra `source_id` và hiệu lực theo `as_of_date`.
- **Session History** lưu bền vững trong SQLite.
- **Long-term Memory** cho hồ sơ ngữ nghĩa người dùng, tách biệt khỏi legal evidence.
- **Admin Ingestion Pipeline** cho PDF, DOCX, DOC, TXT và Markdown.
- **OCR cho PDF scan**, Text Cleaning và Legal Structure Parsing.
- **Background ingestion worker** với tiến trình theo từng stage.
- **Multi-provider LLM**: Groq, OpenAI, OpenRouter và Ollama.
- **SSE Streaming** cho Chat UI.
- **LangFuse observability** tùy chọn.

## Architecture

### Chat Workflow

```text
User
 ↓
Agent Runtime
 ↓
Context Manager
 ↓
Agent Core
 ↓
ReAct Loop
 ├── crag_search
 │     ↓
 │  Chroma + BM25
 │     ↓
 │    RRF
 │     ↓
 │  Reranker
 │     ↓
 │ CRAG Evaluate
 │
 └── controlled_web_search
       ↓
   External Evidence
       ↓
Agent
 ↓
Citation Validator
 ↓
Response
```

### Admin Workflow

```text
Upload
  ↓
Background Worker
  ↓
Parse / OCR
  ↓
Cleaning
  ↓
Structuring
  ↓
Chunking
  ↓
Embedding
  ↓
Chroma + BM25
  ↓
READY
```

### Shared Data Layer

```text
SQLite
├── documents
├── document_chunks
├── ingestion_jobs
├── legal_relations
├── clients
├── sessions
├── messages
└── memories

Chroma
└── Dense vector index

BM25
└── Lexical index
```

> **SQLite là source of truth.** Chroma và BM25 là retrieval indexes có thể rebuild từ các chunk canonical trong SQLite.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13 |
| API | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph |
| LLM Interface | LangChain |
| Relational Storage | SQLite |
| Vector Store | ChromaDB |
| Lexical Retrieval | rank-bm25 |
| Embedding | BAAI/bge-m3 |
| Reranker | BAAI/bge-reranker-v2-m3 |
| Frontend | Next.js 14 + React 18 + TypeScript |
| Styling | Tailwind CSS |
| Package Manager | uv + pnpm 11.18.0 |
| Observability | LangFuse |
| Local LLM | Ollama |

## Project Structure

```text
crag/
├── agent/                  # Agent Core, Runtime, Context Manager, LangGraph
│   ├── graph.py
│   ├── nodes.py
│   ├── state.py
│   ├── runtime.py
│   ├── context.py
│   ├── prompts.py
│   ├── streaming.py
│   └── followups.py
│
├── tools/                  # Agent-visible tools
│   ├── base.py
│   ├── registry.py
│   ├── crag_search.py
│   └── web_search.py
│
├── retrieval/              # Dense, BM25, RRF, Rerank, Refine
├── ingestion/              # Background ingestion pipeline
├── legal/                  # Parser, Cleaner, Citation, Temporal logic
├── memory/                 # Session, History, Semantic Memory
├── providers/              # Provider-specific helpers
├── api/
│   └── main.py             # FastAPI Gateway
├── frontend/               # Next.js Chat + Admin UI
├── eval/                   # Evaluation / benchmark
├── scripts/
├── docs/
│   ├── INSTALL.md
│   ├── SETUP_AND_RUN.md
│   ├── WORKFLOW.md
│   ├── KNOWLEDGE_BASE.md
│   └── TECHNICAL.md
├── config.py
├── llm.py
├── schema.sql
├── init_system.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## Quick Start

### 1. Clone repository

```bash
git clone https://github.com/louisdevzz/crag.git
cd crag
```

### 2. Install backend dependencies

Project được chuẩn hóa với **Python 3.13**:

```bash
uv sync --python 3.13 --frozen
```

Kiểm tra:

```bash
uv run python --version
```

### 3. Install frontend dependencies

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

### 4. Create environment file

```bash
cp .env.example .env
```

Chỉnh `.env` theo provider muốn sử dụng.

Ví dụ với Groq:

```ini
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=your_key
```

Ví dụ với Ollama:

```ini
LLM_PROVIDER=ollama
LLM_MODEL=<model-name>
OLLAMA_BASE_URL=http://localhost:11434
```

### 5. Initialize system

```bash
uv run python init_system.py
```

Runtime data mặc định được lưu dưới:

```text
~/.crag/
```

bao gồm SQLite database, Chroma index, uploaded files và processed data.

## Run

### Backend

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/api/health
```

### Frontend

Terminal khác:

```bash
cd frontend
pnpm dev
```

Mở:

```text
http://localhost:3000
```

## Configuration

Các biến môi trường quan trọng:

```ini
# Chat LLM
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
LLM_TEMPERATURE=0.4

# OCR / Vision
VISION_PROVIDER=groq
VISION_MODEL=qwen/qwen3.8-27b

# Ingestion
INGESTION_WORKERS=3
OCR_CONCURRENCY=4

# Web Search
TINYFISH_API_KEY=

# Retrieval
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# CRAG Thresholds
T_LOW=0.35
T_HIGH=0.70
INTERNAL_STRIP_MIN=0.40

# Local LLM
OLLAMA_BASE_URL=http://localhost:11434

# Optional Observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Xem đầy đủ tại `.env.example`.

## Knowledge Base

Tài liệu được đưa vào hệ thống qua Admin UI hoặc API.

Supported formats:

```text
.pdf
.docx
.doc
.txt
.md
```

Ingestion flow:

```text
Document
   ↓
Parse / OCR
   ↓
Text Cleaning
   ↓
Legal Structure Parser
   ↓
Legal-aware Chunking
   ↓
SQLite
   ↓
Embedding
   ↓
Chroma
   ↓
BM25
   ↓
READY
```

Chỉ document có trạng thái `READY` mới được `crag_search` sử dụng.

### Upload một file

```bash
curl -X POST http://localhost:8000/api/admin/documents/upload \
  -F "file=@/path/to/document.pdf"
```

### Upload nhiều file

```bash
curl -X POST http://localhost:8000/api/admin/documents/upload-batch \
  -F "files=@/path/to/doc1.pdf" \
  -F "files=@/path/to/doc2.docx"
```

## Agent Tools

Agent hiện có đúng hai tool nghiệp vụ:

### `crag_search`

Tra cứu Knowledge Base nội bộ:

```text
Query
 ↓
Dense Retrieval + BM25
 ↓
RRF
 ↓
Rerank
 ↓
CRAG Evaluate
 ↓
Evidence
```

### `controlled_web_search`

Tra cứu nguồn pháp luật ngoài hệ thống khi evidence nội bộ chưa đủ.

Tool chỉ tìm kiếm trên các domain được cho phép và trả evidence về Agent; tool không tự sinh final answer.

## API

Một số endpoint chính:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/chat` | Chat với Agent |
| `POST` | `/api/chat/stream` | Chat qua SSE streaming |
| `GET` | `/api/history/{client_id}` | Conversation history |
| `GET` | `/api/memory/{client_id}` | Semantic memory |
| `GET` | `/api/documents` | READY documents |
| `GET` | `/api/admin/documents` | Admin document list |
| `GET` | `/api/admin/documents/{id}/chunks` | Chunk preview |
| `POST` | `/api/admin/documents/upload` | Upload một document |
| `POST` | `/api/admin/documents/upload-batch` | Upload nhiều document |
| `DELETE` | `/api/admin/documents/{id}` | Xóa document |

## CLI

Chat trực tiếp:

```bash
uv run python main.py
```

Demo:

```bash
uv run python main.py --demo
```

Khởi tạo lại system:

```bash
uv run python main.py --init
```

## Evaluation

Chạy evaluation:

```bash
uv run python eval/run_eval.py
```

Kết quả benchmark phụ thuộc vào corpus, embedding model, reranker, LLM provider và threshold hiện tại, vì vậy không hardcode metric vào README.

## Documentation

| Document | Nội dung |
|---|---|
| [`docs/INSTALL.md`](docs/INSTALL.md) | Cài Git, uv, Python 3.13, NVM, Node.js, pnpm và Ollama |
| [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md) | Cấu hình và chạy project |
| [`docs/WORKFLOW.md`](docs/WORKFLOW.md) | Workflow tổng thể Chat + Admin |
| [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md) | Document, chunk, vector, Chroma và BM25 |
| [`docs/TECHNICAL.md`](docs/TECHNICAL.md) | Technical reference cho developer |
| [`docs/AI_Agent_Corrective_RAG_Memory.pdf`](docs/AI_Agent_Corrective_RAG_Memory.pdf) | Tài liệu tham khảo học thuật của dự án |

## Design Principles

- **No pre-routing:** Agent tự quyết định tool cần gọi.
- **Capability-level tools:** Agent không thao tác trực tiếp SQLite, Chroma hay BM25.
- **CRAG returns evidence, not final answers.**
- **Memory is context, not legal evidence.**
- **SQLite is the canonical source of truth.**
- **Only READY documents are retrievable.**
- **Every legal citation must map to retrieved evidence.**
- **Multi-turn history is persisted in SQLite, not LangGraph in-memory checkpoints.**

## Repository

```text
https://github.com/louisdevzz/crag
```

---

For installation details, start with [`docs/INSTALL.md`](docs/INSTALL.md).  
For architecture and implementation details, see [`docs/TECHNICAL.md`](docs/TECHNICAL.md).

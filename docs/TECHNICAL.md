# Technical Documentation — Legal CRAG Assistant

> Tài liệu kỹ thuật dành cho developer, mô tả cấu trúc mã nguồn, ranh giới module, vòng đời một lượt Agent, Tool Contract, CRAG retrieval, persistence, ingestion và các bất biến kỹ thuật của hệ thống.
>
> Tài liệu này **không phải hướng dẫn cài đặt** và **không lặp lại workflow ở mức người dùng**.  
> Cài môi trường xem [INSTALL.md](INSTALL.md), cách chạy xem [SETUP_AND_RUN.md](SETUP_AND_RUN.md), workflow tổng thể xem [WORKFLOW.md](WORKFLOW.md), kiến trúc Knowledge Base xem [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md).

---

## 1. Mục đích và phạm vi

`TECHNICAL.md` trả lời các câu hỏi ở mức implementation:

- Agent Runtime bắt đầu và kết thúc một turn ở đâu?
- `AgentState` chứa những gì?
- LangGraph thực sự có bao nhiêu node?
- Agent gọi tool theo cơ chế nào?
- `crag_search` làm gì bên trong?
- SQLite, Chroma và BM25 liên kết với nhau ra sao?
- History khác Memory thế nào?
- Ingestion worker đưa một document từ upload đến `READY` như thế nào?
- Provider LLM, Vision và Embedding được tách ra sao?
- Citation Validator kiểm tra điều gì?
- Thành phần nào là source of truth và thành phần nào chỉ là index có thể rebuild?
Kiến trúc hệ thống là **Agentic CRAG theo ReAct loop**, trong đó Agent Core tự chủ quyết định việc tra cứu tri thức nội bộ hoặc tìm kiếm web có kiểm soát dựa trên ngữ cảnh hội thoại.

---

## 2. Kiến trúc tổng thể

Hệ thống có hai runtime flow độc lập dùng chung lớp dữ liệu:

```text
                         Legal CRAG Assistant
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
               Chat Runtime                Admin Runtime
                    │                           │
              Agent Runtime                Ingestion API
                    │                           │
             Context Manager              Background Worker
                    │                           │
               Agent Core                 Ingestion Pipeline
                    │                           │
              Tool Registry                     │
              ┌─────┴─────┐                    │
              ▼           ▼                    │
         crag_search   controlled_web_search    │
              │                                │
              └──────────────┬─────────────────┘
                             ▼
                      Shared Data Layer
                  ┌──────────┼──────────┐
                  ▼          ▼          ▼
                SQLite     Chroma      BM25
```

### Chat Runtime

```text
HTTP / CLI / Eval
       ↓
agent.runtime.prepare_turn()
       ↓
Context Manager
       ↓
LangGraph Agent Core
       ↓
Agent ⇄ Tools
       ↓
Citation Validator
       ↓
agent.runtime.persist_turn()
```

### Admin Runtime

```text
Upload
  ↓
FastAPI Admin Endpoint
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
Chroma Index
  ↓
BM25 Index
  ↓
READY
```

---

## 3. Runtime và Tech Stack

Môi trường phát triển của project được chuẩn hóa như sau:

| Thành phần | Vai trò |
|---|---|
| Python 3.13 | Backend, Agent, retrieval, ingestion |
| `uv` | Python environment và dependency management |
| FastAPI | REST API |
| LangGraph | Agent orchestration |
| LangChain | Model/message/tool interfaces |
| SQLite | Canonical relational storage |
| ChromaDB | Dense vector index |
| `rank-bm25` | Lexical index |
| BGE-M3 | Embedding mặc định |
| BGE Reranker v2 M3 | Reranker mặc định |
| Next.js 14 + React 18 | Frontend |
| pnpm 11.18.0 | Frontend package manager |
| LangFuse | Optional tracing/observability |

`pyproject.toml` hiện cho phép Python `>=3.12`; tài liệu vận hành chuẩn hóa môi trường dự án bằng **Python 3.13**.

---

## 4. Repository Map

Các module chính:

```text
crag/
├── agent/
│   ├── graph.py
│   ├── state.py
│   ├── nodes.py
│   ├── runtime.py
│   ├── context.py
│   ├── prompts.py
│   ├── streaming.py
│   └── followups.py
│
├── tools/
│   ├── base.py
│   ├── registry.py
│   ├── crag_search.py
│   └── web_search.py
│
├── retrieval/
│   ├── dense.py
│   ├── bm25.py
│   ├── fusion.py
│   ├── reranker.py
│   └── refine.py
│
├── ingestion/
│   ├── pipeline.py
│   ├── worker.py
│   ├── indexer.py
│   ├── documents.py
│   ├── chunks.py
│   └── jobs.py
│
├── legal/
│   ├── preprocessor.py
│   ├── cleaner.py
│   ├── parser.py
│   ├── citations.py
│   └── temporal.py
│
├── memory/
│   ├── store.py
│   └── extractor.py
│
├── providers/
│   └── ...
│
├── api/
│   └── main.py
│
├── frontend/
│   └── ...
│
├── config.py
├── llm.py
├── monitoring.py
├── logging_config.py
├── schema.sql
└── main.py
```

### Ranh giới trách nhiệm

| Module | Trách nhiệm |
|---|---|
| `agent/` | Điều phối một turn hội thoại |
| `tools/` | Capability mà Agent được phép gọi |
| `retrieval/` | Dense/BM25/RRF/Rerank/Refine |
| `ingestion/` | Đưa tài liệu vào Knowledge Base |
| `legal/` | Parse, clean, citation, temporal logic |
| `memory/` | Session, message history, semantic memory |
| `providers/`, `llm.py` | Model/provider abstraction |
| `api/` | HTTP boundary |
| `frontend/` | Chat và Admin UI |

---

# 5. Agent Runtime

## 5.1. Entry point của một turn

`agent/runtime.py` là entry point dùng chung cho một lượt hội thoại.

Hai hàm chính:

```text
prepare_turn()
persist_turn()
```

Flow:

```text
query
  ↓
prepare_turn()
  ├── resolve client
  ├── resolve/create session
  ├── extract semantic memory
  └── build context
  ↓
Agent Core
  ↓
persist_turn()
  ├── save user message
  └── save assistant message
```

`invoke_crag()` ghép toàn bộ flow trên cho CLI hoặc các caller không cần tự điều phối.

---

## 5.2. Context Manager

`agent/context.py` chỉ chịu trách nhiệm **lắp context hội thoại**, không retrieval luật.

```text
SQLite messages
      │
      ├── recent messages
      │
      └── semantic memories
      │
      ▼
Context Manager
      │
      ├── conversation_history
      └── memory_context
```

History được lấy từ `messages` theo `session_id`.

Memory được lấy từ `memories` theo `client_id`.

Hai loại dữ liệu này không được trộn vai trò:

```text
History = nội dung hội thoại gần đây
Memory  = hồ sơ ngữ nghĩa dài hạn
Evidence = căn cứ pháp lý đã retrieve
```

Chỉ `Evidence` được dùng làm grounding pháp lý.

---

# 6. AgentState

`agent/state.py` định nghĩa shared state của **một turn**.

Các nhóm field chính:

```text
Request & Context
├── client_id
├── session_id
├── query
├── as_of_date
├── memory_context
└── conversation_history

ReAct Trajectory
├── messages
├── evidence
└── tool_trace

Output
├── generation
├── citation_report
├── follow_up_questions
└── trace_meta
```

### `messages`

```python
messages: Annotated[List[BaseMessage], add_messages]
```

Đây là trajectory nội bộ của ReAct loop trong turn hiện tại:

```text
SystemMessage
HumanMessage
AIMessage(tool_calls)
ToolMessage
AIMessage
...
```

### `evidence`

Evidence được append qua nhiều tool call trong cùng một turn.

```python
evidence: Annotated[List[Dict[str, Any]], operator.add]
```

### `tool_trace`

Lưu trace tóm tắt mỗi tool call:

```text
tool
args
crag_action
success
evidence_count
```
`route` và `crag_action` trả ra API được **suy ra sau khi turn chạy xong** từ `tool_trace` nhằm phục vụ việc theo dõi, kiểm thử và phân tích luồng thực thi.

---

# 7. LangGraph Execution Model

Graph hiện tại có đúng ba node nghiệp vụ:

```text
START
  ↓
agent
  │
  ├── tool_calls ─────→ tools
  │                      │
  │                      └────→ agent
  │
  ├── cần thêm lượt agent ───→ agent
  │
  └── final answer ─────→ cite_validate
                           │
                           ▼
                          END
```

Định nghĩa khái quát:

```text
START -> agent
agent -> tools | agent | cite_validate
tools -> agent
cite_validate -> END
```

### Không có Router

Không tồn tại graph-level routing:

```text
database
rag
general
```

Agent tự quyết định hành động bằng tool calling.

### Không dùng Checkpointer cho multi-turn

Graph được compile không kèm `MemorySaver` hoặc `SqliteSaver`.

Persistence giữa các turn do:

```text
SQLite + Context Manager
```

đảm nhiệm.

LangGraph chỉ giữ state trong lifecycle của turn đang chạy.

---

# 8. Agent Node và ReAct Loop

`agent/nodes.py::agent_node()` thực hiện một lượt model call.

Flow:

```text
build messages
     ↓
get chat model
     ↓
count tool rounds
     ↓
bind tools nếu chưa đạt giới hạn
     ↓
LLM call
     ↓
tool_calls?
 /         \
yes         no
 │           │
tools       parse final answer
```

## 8.1. Tool round limit

Hệ thống có:

```python
MAX_TOOL_ROUNDS = 3
```

Khi đạt giới hạn, tool schema không còn được cung cấp cho model. Model phải tổng hợp câu trả lời từ evidence hiện có hoặc abstain.

Ngoài ra có giới hạn riêng cho corrective nudge khi CRAG báo evidence chưa đủ.

Mục tiêu của hai giới hạn:

- tránh loop vô hạn;
- tránh cùng một query bị gọi tool liên tục;
- ép Agent kết thúc turn một cách xác định.

## 8.2. Duplicate tool-call protection

`tool_node()` kiểm tra `(tool_name, args)` đã được thực thi thành công trong turn chưa.

Nếu trùng:

```text
Không execute lại
↓
trả ToolMessage nhắc model dùng evidence cũ
```

Điều này đặc biệt quan trọng với Web Search vì tránh network call lặp.

## 8.3. Tool-call recovery

Nếu provider không trả structured `tool_calls` đúng chuẩn nhưng leak function markup vào text, Agent có logic phục hồi tool call trước khi tiếp tục.

Đây là lớp compatibility cho các model/tool-call implementation không hoàn toàn đồng nhất.

---

# 9. Tool System

Agent chỉ nhìn thấy hai capability:

```text
Tool Registry
├── crag_search
└── controlled_web_search
```

Không expose trực tiếp:

```text
SQLite query
Chroma search
BM25 search
RRF
Reranker
Embedding
```

Các thành phần trên là implementation detail.

---

## 9.1. BaseLegalTool

Mọi tool kế thừa `BaseLegalTool`.

Tool contract:

```text
Input
  ↓
Pydantic args_schema validation
  ↓
execute()
  ↓
ToolResult
```

`ToolResult`:

```python
{
    "tool_name": str,
    "success": bool,
    "data": Any,
    "error": str | None,
    "execution_time_ms": float,
    "metadata": dict
}
```

Tool không được ném lỗi trực tiếp lên Agent cho các lỗi runtime thông thường; `BaseLegalTool.run()` đóng gói lỗi vào `ToolResult`.

---

## 9.2. Tool Registry

`tools/registry.py` chịu trách nhiệm:

```text
register tool
get tool
list tools
execute tool
export OpenAI-compatible schemas
```

Agent không import từng tool cụ thể vào prompt.

Agent nhận schema từ:

```python
registry.to_openai_tools()
```

---

# 10. `crag_search`

`crag_search` là capability truy vấn kho tri thức pháp lý nội bộ.

Pipeline chuẩn:

```text
Query
  │
  ├──────────────┐
  ▼              ▼
Dense          BM25
Chroma         Lexical
  │              │
  └──────┬───────┘
         ▼
        RRF
         ↓
      Rerank
         ↓
   CRAG Decision
         ↓
  Refine Internal
         ↓
      Evidence
```

Output mức tool:

```json
{
  "crag_action": "CORRECT | AMBIGUOUS | INCORRECT",
  "guidance": "...",
  "evidence": [],
  "dense_candidates": 0,
  "bm25_candidates": 0
}
```

Tool **không sinh final answer**.

---

## 10.1. Dense Retrieval

`retrieval/dense.py` sử dụng Chroma.

```text
query
 ↓
embedding function
 ↓
Chroma similarity search
 ↓
top-k semantic candidates
```

Candidate chứa các metadata quan trọng:

```text
evidence_id
document_id
document_number
document_title
chapter
article
clause
heading
text
score
```

---

## 10.2. BM25 Retrieval

`retrieval/bm25.py` sử dụng `rank-bm25`.

BM25 phù hợp với các pattern exact lexical như:

```text
Điều 25
Khoản 2
41/2024/QH15
giấy phép lao động
```

BM25 index được load từ file:

```text
~/.crag/data/processed/bm25_index.pkl
```

theo cấu hình mặc định tương ứng với `PROCESSED_DATA_DIR`.

Index được cache trong process và invalidated khi rebuild.

---

## 10.3. Reciprocal Rank Fusion

`retrieval/fusion.py` hợp nhất Dense và BM25 theo RRF.

Công thức:

```text
RRF(d) = Σ 1 / (k + rank(d))
```

`k` lấy từ cấu hình `RRF_K`.

RRF dùng ranking position thay vì cố gắng so sánh trực tiếp cosine score với BM25 score.

---

## 10.4. Reranker

`retrieval/reranker.py` rerank candidate theo cặp:

```text
(query, chunk)
```

Ưu tiên:

1. FlagEmbedding reranker nếu khả dụng.
2. `sentence-transformers` CrossEncoder.
3. Token-overlap heuristic fallback nếu model reranker không load được.

Điểm cuối được normalize về khoảng:

```text
0.0 → 1.0
```

---

## 10.5. CRAG Decision

Evaluator dùng best reranker score và hai threshold:

```text
score >= T_HIGH
    → CORRECT

score <= T_LOW
    → INCORRECT

T_LOW < score < T_HIGH
    → AMBIGUOUS
```

Threshold lấy từ config/.env, không hardcode trong Agent graph.

Ý nghĩa:

| Action | Ý nghĩa |
|---|---|
| `CORRECT` | Evidence nội bộ đủ mạnh |
| `AMBIGUOUS` | Có liên quan nhưng chưa chắc đủ |
| `INCORRECT` | Corpus nội bộ không đủ căn cứ |

CRAG trả thêm `guidance` để model quyết định bước tiếp theo.

---

## 10.6. Exact Article Fast Path

Nếu query có locator rõ:

```text
Điều 7
Điều 25
...
```

`crag_search` có fast-path truy vấn các chunk tương ứng trong SQLite để ưu tiên đúng điều được người dùng nhắc tới.
Cơ chế này được tích hợp trực tiếp bên trong `crag_search` nhằm tối ưu độ chính xác khi người dùng nhắc đích danh một Điều luật cụ thể.

---

## 10.7. Knowledge Refinement

`retrieval/refine.py` chia candidate thành các legal strip nhỏ hơn và rerank lại.

Flow:

```text
candidate chunk
    ↓
split_into_legal_strips()
    ↓
rerank strips
    ↓
filter by INTERNAL_STRIP_MIN
    ↓
evidence
```

Mục tiêu là đưa cho Agent đoạn căn cứ ngắn, cụ thể hơn thay vì toàn bộ chunk dài.

---

# 11. `controlled_web_search`

Tool này chỉ dùng cho evidence ngoài corpus.

Flow:

```text
Agent-generated search query
        ↓
TinyFish Search API
        ↓
official-domain filtering
        ↓
fetch page
        ↓
clean HTML
        ↓
refine_external()
        ↓
Web Evidence
```

Nguồn được giới hạn bởi allow-list `OFFICIAL_DOMAINS`.

Ví dụ domain:

```text
vbpl.vn
chinhphu.vn
moj.gov.vn
...
```

Web Search không tự động chạy chỉ vì CRAG trả `INCORRECT`.

CRAG đưa `guidance`; **Agent Core vẫn là thành phần quyết định có gọi `controlled_web_search` hay không**.

Đây là điểm giữ đúng semantics của Agentic CRAG:

```text
CRAG evaluates
Agent decides
Tool executes
```

---

# 12. Evidence Contract

Tool result được chuyển thành `ToolMessage`.

Agent không nhận toàn bộ object nội bộ; các trường evidence chính được đưa vào conversation:

```json
{
  "source_id": "...",
  "heading": "...",
  "text": "..."
}
```

Trong `AgentState`, evidence đầy đủ vẫn được tích lũy để:

- Citation Validator kiểm tra;
- API trả evidence card;
- logging/trace;
- persistence vào `messages.evidence_json`.

Một evidence identifier có thể đến từ:

```text
strip_id
locator
evidence_id
```

Các ID phải ổn định trong một corpus version để citation có thể truy ngược.

---

# 13. Citation Validation

`legal/citations.py` là deterministic validator chạy sau khi Agent đã sinh answer.

```text
Generation
   ↓
build evidence_map
   ↓
validate source_id
   ↓
validate temporal effectiveness
   ↓
Citation Report
```

Validator kiểm tra:

1. `source_id` có tồn tại trong evidence không.
2. Citation có match được locator/parent locator không.
3. Nếu có `as_of_date`, evidence có hiệu lực tại ngày đó không.
4. Claim nào có citation hợp lệ.
5. Citation accuracy và coverage.

Report:

```text
ok
errors
valid_citations
total_citations
total_claims
claims_with_valid_citation
citation_accuracy
citation_coverage
```

Nếu answer không `abstain` nhưng không có claim có căn cứ, validator đánh dấu lỗi.

---

# 14. History, Session và Memory

Ba khái niệm phải giữ riêng biệt.

## 14.1. Session

Bảng:

```text
sessions
```

Mỗi session thuộc một `client_id`.

Session được create/touch ở đầu turn.

---

## 14.2. History

Canonical short-term history nằm trong:

```text
messages
```

Mỗi user/assistant response là một row.

Context Manager đọc recent messages để tạo:

```text
conversation_history
```

Không dùng `query_logs` làm history canonical.

---

## 14.3. Semantic Memory

Long-term profile nằm trong:

```text
memories
```

Memory bị giới hạn bởi:

```text
ALLOWED_MEMORY_KEYS
```

Ví dụ:

```text
business_type
industry
province
```

Memory dùng để hiểu context kiểu:

```text
"công ty tôi"
"doanh nghiệp của tôi"
```

Memory **không được dùng làm legal evidence**.

---

# 15. SQLite Schema

SQLite chia thành hai domain.

## Corpus / Admin

```text
documents
document_chunks
ingestion_jobs
legal_relations
```

## Conversation / Chat

```text
clients
sessions
messages
memories
```

Quan hệ chính:

```text
clients
   └── sessions
          └── messages

clients
   └── memories

documents
   ├── document_chunks
   ├── ingestion_jobs
   └── legal_relations
```

SQLite chạy với:

```text
foreign_keys = ON
journal_mode = WAL
busy_timeout
```

để phù hợp với concurrent API read/write và ingestion worker.

---

# 16. Source of Truth và Retrieval Indexes

Nguyên tắc quan trọng:

```text
SQLite = source of truth
Chroma = dense retrieval index
BM25   = lexical retrieval index
```

## SQLite

Lưu canonical chunk:

```text
document_chunks.id
document_id
chapter
article
clause
point
heading
content
page_start
page_end
```

## Chroma

Lưu:

```text
id = document_chunks.id
text
embedding vector
metadata
```

`ingestion/indexer.py` dùng `document_chunks.id` làm vector ID.

## BM25

Được rebuild từ toàn bộ chunk thuộc document có:

```text
status = READY
```

Do Chroma và BM25 là indexes, cả hai có thể rebuild từ SQLite mà không cần parse lại file gốc nếu chunk canonical còn nguyên.

---

# 17. Ingestion Architecture

Admin upload không chạy toàn pipeline trong HTTP request.

```text
POST upload
   ↓
save file
   ↓
create documents row
   ↓
create ingestion_jobs row
   ↓
submit background worker
   ↓
return HTTP response
```

Worker chạy pipeline sau đó.

---

## 17.1. Background Worker

`ingestion/worker.py` dùng:

```python
ThreadPoolExecutor
```

Số worker:

```text
INGESTION_WORKERS
```

Mặc định hiện tại:

```text
3
```

### Single upload

```text
submit_ingestion(document_id)
```

### Batch upload

```text
submit_batch_ingestion(document_ids)
```

Với batch, từng document được xử lý song song nhưng BM25 chỉ rebuild một lần khi toàn batch hoàn tất.

---

# 18. Ingestion Pipeline

`ingestion/pipeline.py` chạy các stage:

```text
PARSING
  ↓
OCR (nếu cần)
  ↓
CLEANING
  ↓
STRUCTURING
  ↓
CHUNKING
  ↓
EMBEDDING
  ↓
INDEXING
  ↓
DONE
```

Document lifecycle:

```text
UPLOADED
   ↓
PROCESSING
   ↓
READY
```

Nếu lỗi:

```text
FAILED
```

---

## 18.1. Parsing và OCR

PDF được kiểm tra từng page.

Nếu page không có usable digital text:

```text
OCR required
```

`UniversalLegalPreprocessor` xử lý text extraction/OCR.

Progress được ghi vào job:

```text
OCR trang 12/45
```

---

## 18.2. Cleaning

`legal/cleaner.py` làm sạch format noise trước khi parse cấu trúc.

Loại các thành phần như:

```text
dot leaders
table-of-contents noise
standalone page numbers
Unicode invisible chars
whitespace dư
footer/header noise phù hợp rule
```

Không được phá các locator pháp lý:

```text
Điều 7.
1.
a)
219/2025/NĐ-CP
```

---

## 18.3. Structuring

`legal/parser.py` nhận diện:

```text
Chương
Mục
Điều
Khoản
Điểm
```

và gắn page range.

---

## 18.4. Chunking

Provisions được ghi vào:

```text
document_chunks
```

Một chunk có canonical ID và legal metadata.

Đây là đơn vị sau đó được:

```text
embed
index
retrieve
cite
```

---

## 18.5. Embedding + Chroma

`index_document_chunks()`:

1. Xóa vector cũ của document.
2. Lấy chunk canonical từ SQLite.
3. Chỉ lấy document đang ở trạng thái `READY`.
4. Embed theo batch.
5. Ghi text + vector + metadata vào Chroma.

Batch size hiện tại:

```text
64 chunks
```

Progress:

```text
Đang nhúng đoạn N/M
```

---

## 18.6. BM25 Rebuild

BM25 được rebuild từ:

```text
all READY document chunks
```

Sau rebuild, in-process BM25 cache bị invalidated để request tiếp theo load index mới.

---

## 18.7. Failure Cleanup

Nếu pipeline lỗi:

```text
exception
  ↓
remove partial Chroma vectors
  ↓
rebuild BM25 khi cần
  ↓
documents.status = FAILED
  ↓
store error_message
```

Nguyên tắc:

> Document FAILED không được để lại partial retrieval state làm Agent retrieve nhầm.

---

# 19. Provider Layer

Chat LLM và Embedding Provider là hai abstraction riêng.

```text
Provider Layer
├── Chat LLM
│   ├── Groq
│   ├── OpenAI
│   ├── OpenRouter
│   └── Ollama
│
└── Embedding
    ├── Hugging Face / sentence-transformers
    ├── OpenAI
    └── Ollama
```

---

## 19.1. Chat Model Factory

`llm.py::get_chat_model()` tạo LangChain `BaseChatModel`.

`get_chat_model_with_fallback()`:

```text
primary provider
      ↓
success?
 /        \
yes        no
 │          ↓
return   fallback providers
```

Nếu tất cả provider fail, Agent dùng deterministic evidence fallback thay vì crash toàn turn.

---

## 19.2. Embedding Factory

`get_embeddings()` cache embedding instance theo:

```text
(provider, model)
```

Embedding model không phụ thuộc Chat LLM.

Ví dụ hợp lệ:

```text
Chat LLM     = Groq
Embedding    = Hugging Face BGE-M3
Reranker     = BGE Reranker
```

hoặc:

```text
Chat LLM     = Ollama
Embedding    = Ollama
```

---

# 20. API Contracts

FastAPI entry:

```text
api/main.py
```

## Chat

| Method | Endpoint | Vai trò |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/chat` | Non-streaming Agent turn |
| `POST` | `/api/chat/stream` | SSE streaming Agent turn |
| `GET` | `/api/history/{client_id}` | Conversation history |
| `DELETE` | `/api/history/{client_id}/{session_id}` | Xóa một session |
| `DELETE` | `/api/history/{client_id}` | Xóa history của client |
| `GET` | `/api/memory/{client_id}` | Semantic memory |
| `DELETE` | `/api/memory/{client_id}` | Xóa semantic memory |
| `GET` | `/api/documents` | READY documents |

## Admin

| Method | Endpoint | Vai trò |
|---|---|---|
| `GET` | `/api/admin/documents` | Danh sách toàn bộ document |
| `GET` | `/api/admin/documents/{id}` | Metadata + ingestion job |
| `GET` | `/api/admin/documents/{id}/chunks` | Chunk preview |
| `GET` | `/api/admin/stats` | Corpus statistics |
| `POST` | `/api/admin/documents/upload` | Upload một file |
| `POST` | `/api/admin/documents/upload-batch` | Upload batch |
| `DELETE` | `/api/admin/documents/{id}` | Xóa document khỏi SQLite/Chroma/BM25 |

Admin API không expose vector raw cho UI.

---

# 21. Streaming

`POST /api/chat/stream` sử dụng Server-Sent Events.

Các loại event chính:

```text
node
tool_start
tool_end
token
done
error
```

Frontend có thể hiển thị:

```text
Agent đang suy luận
CRAG đang retrieve
Web Search đang chạy
Citation Validator đang kiểm tra
```

mà không cần biết chi tiết implementation bên trong từng tool.

---

# 22. Observability

Có hai lớp observability.

## 22.1. Application Logs

`logging_config.py` cung cấp:

```text
get_logger()
timed_stage()
```

Ví dụ stage:

```text
AGENT:LLM_CALL
AGENT:TOOL_CALL
RETRIEVE:DENSE
RETRIEVE:BM25
RETRIEVE:RRF
RETRIEVE:RERANK
INGEST:OCR
INGEST:CHUNKING
INGEST:EMBEDDING
```

`timed_stage()` log:

```text
start
done + elapsed time
FAILED + elapsed time
```

## 22.2. LangFuse

`monitoring.py` bật LangFuse khi có:

```text
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
```

Nếu không cấu hình, tracing tự disable và ứng dụng vẫn chạy.

LangFuse metadata gồm:

```text
thread/session id
client id
trace name
```

---

# 23. Frontend Architecture

Frontend:

```text
Next.js 14
React 18
TypeScript
Tailwind CSS
```

Có hai chức năng chính:

```text
Chat Page
Admin Page
```

## Chat Page

Giao tiếp với:

```text
/api/chat
/api/chat/stream
/api/history
/api/memory
```

## Admin Page

Giao tiếp với:

```text
/api/admin/documents
/api/admin/documents/{id}
/api/admin/documents/{id}/chunks
/api/admin/stats
/api/admin/documents/upload
```

Admin chỉ hiển thị:

```text
document
status
progress
error
chunk preview
```

Không expose:

```text
embedding vector
vector dimensions
Chroma internals
BM25 internals
```

---

# 24. Error Handling

Các lỗi được xử lý tại boundary phù hợp.

### LLM unavailable

```text
Provider Manager
   ↓
try fallback providers
   ↓
all failed
   ↓
deterministic evidence fallback
```

### Tool error

```text
Tool exception
   ↓
BaseLegalTool.run()
   ↓
ToolResult(success=False)
   ↓
ToolMessage
```

### Retrieval model unavailable

Embedding init failure được báo rõ; không sinh dummy embedding.

Reranker có heuristic fallback nếu CrossEncoder không khả dụng.

### Ingestion error

```text
FAILED
+ error_message
+ remove partial vectors
```

### Web Search unavailable

Nếu `TINYFISH_API_KEY` không được cấu hình hoặc request fail, tool trả empty evidence thay vì làm crash API process.

---

# 25. Testing Strategy

Test nên chia theo boundary.

## Unit Tests

```text
legal.cleaner
legal.parser
retrieval.fusion
retrieval.reranker
legal.citations
memory.store
tool schemas
```

## Retrieval Tests

Kiểm tra:

```text
Dense top-k
BM25 exact locator
RRF ordering
Rerank
CRAG action
```

## Agent Tests

Kiểm tra:

```text
No Router
tool selection
tool loop bound
duplicate tool call protection
abstain
citation validation
```

## Ingestion Tests

Kiểm tra:

```text
upload
duplicate hash
parse
OCR routing
cleaning
chunk creation
Chroma indexing
BM25 rebuild
FAILED cleanup
```

## API Tests

Kiểm tra:

```text
/api/chat
/api/chat/stream
history isolation
memory isolation
admin upload
admin chunk preview
```

## Evaluation

`eval/` dùng để đánh giá các chỉ số retrieval và grounding.

Kết quả benchmark không nên hardcode vào tài liệu kỹ thuật vì thay đổi theo:

```text
corpus
model
threshold
embedding
reranker
provider
```

---

# 26. Technical Invariants

Các rule dưới đây là ranh giới developer không nên phá.

### 1. Không thêm Router trước Agent Core

Sai:

```text
User
 ↓
Router
 ├── DB
 ├── RAG
 └── General
```

Đúng:

```text
User
 ↓
Agent
 ↓
Agent tự chọn tool
```

### 2. Chỉ expose capability-level tools

Agent-visible:

```text
crag_search
controlled_web_search
```

Không expose storage primitive:

```text
sqlite_query
chroma_search
bm25_search
```

### 3. CRAG không sinh final answer

```text
CRAG
→ evidence
→ Agent
→ answer
```

### 4. Memory không phải legal evidence

```text
Memory → context only
Evidence → legal grounding
```

### 5. SQLite là canonical source

```text
SQLite
 ↓
rebuild
 ├── Chroma
 └── BM25
```

### 6. Chỉ READY document được retrieve

Document `PROCESSING` hoặc `FAILED` không được xuất hiện trong Knowledge Base phục vụ Chat.

### 7. Citation phải map về evidence thật

Không chấp nhận model tự tạo `source_id`.

### 8. Multi-turn persistence thuộc SQLite

Không dùng LangGraph in-memory checkpointer như source of truth cho conversation history.

### 9. Chat provider và embedding provider độc lập

Thay LLM không được bắt buộc rebuild vector nếu embedding model không đổi.

### 10. Admin không phụ thuộc Agent Core

Ingestion là deterministic pipeline riêng, không chạy qua ReAct graph.

---

# 27. Dependency Direction

Dependency mong muốn:

```text
api
 ↓
agent runtime
 ↓
agent core
 ↓
tools
 ↓
retrieval
 ↓
storage/index
```

Admin:

```text
api
 ↓
ingestion
 ↓
legal parser/cleaner
 ↓
storage/index
```

Không nên để:

```text
retrieval -> api
storage -> agent
ingestion -> frontend
```

Module tầng thấp không được phụ thuộc ngược vào tầng giao diện.

---

# 28. Tóm tắt kiến trúc kỹ thuật

```text
                         CHAT
                          │
                    Agent Runtime
                          │
                   Context Manager
                          │
                      Agent Core
                          │
                     ReAct Loop
                   ┌──────┴──────┐
                   ▼             ▼
              crag_search     web_search
                   │
          ┌────────┴────────┐
          ▼                 ▼
       Chroma              BM25
          └────────┬────────┘
                   ▼
                  RRF
                   ↓
                Rerank
                   ↓
             CRAG Evaluate
                   ↓
                Evidence
                   │
                   └──────→ Agent
                              ↓
                       Citation Validator
                              ↓
                           Response


                         ADMIN
                           │
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


                    SHARED DATA
              ┌────────┬────────┬────────┐
              ▼        ▼        ▼
            SQLite   Chroma    BM25
```

---

# 29. Tài liệu liên quan

- [INSTALL.md](INSTALL.md) — cài Git, uv, Python 3.13, NVM, Node.js, pnpm, Ollama.
- [SETUP_AND_RUN.md](SETUP_AND_RUN.md) — cấu hình `.env` và chạy project.
- [WORKFLOW.md](WORKFLOW.md) — workflow Chat + Admin ở mức hệ thống.
- [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) — chi tiết document → chunk → vector → retrieval.

```text
INSTALL.md
    ↓
SETUP_AND_RUN.md
    ↓
┌───────────────┬───────────────────┐
▼               ▼                   ▼
TECHNICAL.md   WORKFLOW.md     KNOWLEDGE_BASE.md
```

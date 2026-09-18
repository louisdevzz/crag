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
* Tra cứu Knowledge Base nội bộ bằng `crag_search`;
* Tìm kiếm nguồn pháp luật ngoài hệ thống bằng `controlled_web_search`;
* Trả lời trực tiếp khi không cần gọi công cụ.

Các câu trả lời pháp lý được kiểm tra lại bằng **Deterministic Citation Validator** trước khi trả về cho người dùng.

## System Architecture

### 1. Kiến trúc Tổng thể Hệ thống (Chat + Admin + Shared Layer)

![Agentic CRAG Architecture](docs/images/agent-crag-architecture.png)

### 2. Luồng Hoạt động Chi tiết Toàn diện (End-to-End Workflow)

![Legal CRAG Detailed Workflow](docs/images/workflow.png)

## Key Features

* **Agentic ReAct Loop** với LangGraph: `agent ⇄ tools`.
* **Corrective RAG 3 trạng thái**: `CORRECT`, `AMBIGUOUS`, `INCORRECT`.
* **Hybrid Retrieval**: Dense Retrieval với Chroma (BGE-M3 1024 chiều) + Lexical Retrieval với BM25.
* **Reciprocal Rank Fusion (RRF)** ($k=60$) và Cross-Encoder Sigmoid Reranking.
* **Controlled Web Search** giới hạn nguồn pháp luật theo tên miền nhà nước (`vbpl.vn`, `chinhphu.vn`...).
* **Citation Validation** kiểm tra `source_id` và hiệu lực theo `as_of_date`.
* **Session History** lưu bền vững trong SQLite.
* **Long-term Memory** cho hồ sơ ngữ nghĩa người dùng, tách biệt khỏi legal evidence.
* **Admin Ingestion Pipeline** cho PDF, DOCX, DOC, TXT và Markdown.
* **OCR cho PDF scan** qua Vision LLM đa luồng (`OCR_CONCURRENCY = 4`), Text Cleaning và Legal Structure Parsing.
* **Background Ingestion Worker** với tiến trình thời gian thực.
* **Multi-provider LLM**: Groq, OpenAI, OpenRouter và Ollama.
* **SSE Streaming** cho Chat UI.
* **LangFuse Observability** tích hợp giám sát vết.

## Tech Stack

| Phân hệ | Công nghệ |
| :--- | :--- |
| **Ngôn ngữ Nền tảng** | Python 3.13 |
| **API Gateway** | FastAPI + Uvicorn |
| **Điều phối Tác tử** | LangGraph |
| **Khung Tác tử** | LangChain Core |
| **Cơ sở Dữ liệu Quan hệ** | SQLite (Source of Truth) |
| **Vector Database** | ChromaDB |
| **Lexical Search** | rank-bm25 (BM25Okapi) |
| **Mô hình Embedding** | BAAI/bge-m3 (1024 chiều) |
| **Mô hình Reranker** | BAAI/bge-reranker-v2-m3 (Cross-Encoder Sigmoid) |
| **Giao diện Người dùng** | Next.js 14 + React 18 + TypeScript |
| **Styling** | Tailwind CSS |
| **Quản lý Gói** | uv (Python) + pnpm 11.18.0 (Node.js) |
| **Giám sát Thực thi** | LangFuse |
| **Mô hình Local On-premise** | Ollama |

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
├── eval/                   # Evaluation & Benchmark (RAGAS, Baselines S0-S4)
├── scripts/
│   ├── ingest_folder.py    # Script nạp tài liệu từ thư mục
│   ├── init_system.py      # Khởi tạo database và kiểm tra môi trường
│   ├── pull_models.py      # Tải trước trọng số mô hình
│   └── render_mermaid.py   # Kết xuất sơ đồ Mermaid ra PNG/SVG
├── data/
│   └── raw/                # Kho dữ liệu văn bản pháp quy gốc (505 tệp)
├── docs/                   # Tài liệu đặc tả kỹ thuật và kiến trúc
├── config.py
├── llm.py
├── schema.sql
├── init_system.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## Documentation

Toàn bộ hướng dẫn chi tiết về cài đặt, cấu hình và kiến trúc được phân tách rõ ràng trong thư mục `docs/`:

| Tài liệu | Nội dung chi tiết |
| :--- | :--- |
| [`docs/INSTALL.md`](docs/INSTALL.md) | **Hướng dẫn cài đặt công cụ:** Git, uv, Python 3.13, NVM, Node.js, pnpm và Ollama |
| [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md) | **Hướng dẫn cấu hình & khởi chạy:** Thiết lập `.env`, khởi tạo database, chạy Backend API, Frontend UI và CLI |
| [`docs/WORKFLOW.md`](docs/WORKFLOW.md) | **Đặc tả luồng hoạt động & kiến trúc:** Chi tiết Chat Workflow, Ingestion Pipeline và Data Models |
| [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md) | **Đặc tả kho tri thức:** Cơ chế phân đoạn Legal-aware Chunking, SQLite schema và chỉ mục kép |
| [`docs/RUBRIC_COMPLIANCE.md`](docs/RUBRIC_COMPLIANCE.md) | **Báo cáo đối soát Rubric:** Bảng đối chiếu chi tiết các tiêu chí chấm điểm của đề bài |
| [`docs/TECHNICAL.md`](docs/TECHNICAL.md) | **Đặc tả kỹ thuật sâu:** Dành cho developer, mô tả chi tiết interface và giải thuật |

## CLI & Evaluation

### Giao diện Dòng lệnh (CLI)
* Chat trực tiếp từ Terminal: `uv run python main.py`
* Chạy bộ 5 kịch bản thực nghiệm Demo: `uv run python main.py --demo`
* Nạp toàn bộ tài liệu từ thư mục vào kho tri thức: `uv run python scripts/ingest_folder.py data/raw/` (hoặc `uv run python main.py --ingest-folder data/raw/`)

### Đánh giá Thực nghiệm (Evaluation & RAGAS Benchmark)
* Đo lường hiệu năng và đối chiếu ma trận các hệ thống Baseline (S0: LLM-only, S1: Traditional RAG, S2: RAG + Always Web, S4: Full CRAG đề xuất):
```bash
uv run python eval/run_eval.py --baselines --sample-limit 5
```
* Đo lường các chỉ số RAGAS chuẩn hóa (Faithfulness, Answer Relevancy, Context Precision, Context Recall):
```bash
uv run python eval/run_eval.py --test
```
* Quét lưới hiệu chuẩn ngưỡng $(T_{low}, T_{high})$:
```bash
uv run python eval/run_eval.py --calibration
```
* Toàn bộ kết quả thực nghiệm được tự động lưu trữ tại `eval/benchmark_report.json`.

## Core Design Principles

* **No pre-routing:** Agent tự chủ quyết định việc gọi công cụ thông qua cơ chế Function Calling của LLM.
* **Capability-level tools:** Agent chỉ tương tác với công cụ nghiệp vụ (`crag_search`, `controlled_web_search`), không thao tác trực tiếp với tầng kỹ thuật SQLite, Chroma hay BM25.
* **CRAG returns evidence, not final answers:** Công cụ CRAG chỉ cung cấp các mảnh bằng chứng và lời chỉ dẫn (*guidance*), Agent giữ quyền tổng hợp câu trả lời.
* **Memory is context, not legal evidence:** Semantic Memory chỉ dùng để hiểu ngữ cảnh khách hàng, tuyệt đối không dùng làm căn cứ pháp lý.
* **SQLite is the canonical source of truth:** Toàn bộ văn bản và đoạn trích lưu trữ gốc tại SQLite; ChromaDB và BM25 đóng vai trò chỉ mục tìm kiếm có thể tái tạo bất kỳ lúc nào.
* **Only READY documents are retrievable:** Chỉ tài liệu đã nạp thành công mới được đưa vào không gian tìm kiếm.
* **Zero citation hallucination:** Mọi mệnh đề kết luận pháp lý bắt buộc phải có trích dẫn nguồn kiểm chứng được và còn hiệu lực tại ngày tham chiếu `as_of_date`.

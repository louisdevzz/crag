# Setup & Run — Legal CRAG Assistant

> Tài liệu này hướng dẫn **cấu hình và chạy dự án sau khi đã cài các công cụ hệ thống**.  
> Nếu máy chưa có Git, `uv`, Python 3.13, NVM, Node.js, pnpm hoặc Ollama, xem [INSTALL.md](INSTALL.md) trước.

## 1. Chuẩn bị repository

Nếu chưa clone:

```bash
git clone https://github.com/louisdevzz/crag.git
cd crag
```

Nếu đã có repository:

```bash
cd crag
git pull
```

Tất cả lệnh backend bên dưới được chạy từ thư mục gốc `crag/`.

## 2. Cài dependencies backend

Dự án chuẩn hóa môi trường bằng **Python 3.13** và dùng `uv.lock` để đồng bộ dependency.

```bash
uv sync --python 3.13 --frozen
```

Kiểm tra:

```bash
uv run python --version
```

Kết quả mong đợi:

```text
Python 3.13.x
```

Không cần `source .venv/bin/activate` nếu dùng các lệnh `uv run ...`.

## 3. Cài dependencies frontend

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

Kiểm tra:

```bash
node --version
pnpm --version
```

Frontend hiện khai báo `pnpm 11.18.0`.

## 4. Tạo file cấu hình

Từ thư mục `crag/`:

```bash
cp .env.example .env
```

Sau đó chỉnh `.env` theo provider muốn sử dụng.

### Groq

```ini
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=your_key
```

### OpenAI

```ini
LLM_PROVIDER=openai
LLM_MODEL=<openai-model>
OPENAI_API_KEY=your_key
```

### OpenRouter

```ini
LLM_PROVIDER=openrouter
LLM_MODEL=<openrouter-model>
OPENROUTER_API_KEY=your_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### Ollama local

Đảm bảo Ollama đang chạy:

```bash
ollama list
```

Sau đó cấu hình:

```ini
LLM_PROVIDER=ollama
LLM_MODEL=<model-name>
OLLAMA_BASE_URL=http://localhost:11434
```

`LLM_MODEL` phải trùng với tên hiển thị bởi `ollama list`.

## 5. Các cấu hình quan trọng khác

### OCR cho PDF scan

```ini
VISION_PROVIDER=groq
VISION_MODEL=qwen/qwen3.8-27b

INGESTION_WORKERS=3
OCR_CONCURRENCY=4
```

Nếu dùng provider cloud cho OCR, cần API key tương ứng.

### Web Search

```ini
TINYFISH_API_KEY=your_tinyfish_api_key
```

`controlled_web_search` cần key này khi Agent quyết định tìm thêm nguồn pháp luật trên web.

### Embedding và Reranker

```ini
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

Hai model này phục vụ retrieval nội bộ và độc lập với `LLM_PROVIDER`.

### Storage

Mặc định runtime data nằm dưới:

```text
~/.crag/
```

Có thể thay đổi bằng:

```ini
CRAG_HOME=~/.crag
DB_PATH=~/.crag/app.db
CHROMA_DIR=~/.crag/chroma
```

### LangFuse

Tùy chọn:

```ini
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

## 6. Khởi tạo hệ thống

Chạy một lần sau khi setup môi trường:

```bash
uv run python init_system.py
```

Lệnh này khởi tạo runtime storage, SQLite và các thư mục cần thiết dưới `~/.crag/`.

Kiểm tra:

```bash
ls -la ~/.crag
```

## 7. Chạy backend FastAPI

Terminal 1, từ thư mục `crag/`:

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra:

```bash
curl http://localhost:8000/api/health
```

Swagger:

```text
http://localhost:8000/docs
```

Backend:

```text
http://localhost:8000
```

## 8. Chạy frontend

Terminal 2:

```bash
cd crag/frontend
pnpm dev
```

Mở:

```text
http://localhost:3000
```

Development flow:

```text
Frontend :3000
     ↓
FastAPI  :8000
```

Backend đã bật CORS cho frontend development.

## 9. Chạy nhanh sau lần setup đầu tiên

### Terminal 1 — Backend

```bash
cd crag
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend

```bash
cd crag/frontend
pnpm dev
```

Nếu dùng Ollama local, đảm bảo `ollama list` không báo lỗi kết nối.

## 10. Admin — nạp tài liệu vào Knowledge Base

Mở Admin Page trên frontend và upload tài liệu.

Backend hiện chấp nhận:

```text
.pdf
.docx
.doc
.txt
.md
```

Pipeline:

```text
Upload
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
Chroma
  ↓
BM25
  ↓
READY
```

Admin chỉ cần quan sát:

- file đã upload;
- trạng thái xử lý;
- tiến trình hiện tại;
- lỗi nếu có;
- chunk sau khi hoàn tất.

Embedding và indexing là bước nội bộ.

### Upload một file bằng API

```bash
curl -X POST http://localhost:8000/api/admin/documents/upload   -F "file=@/path/to/document.pdf"
```

### Upload nhiều file

```bash
curl -X POST http://localhost:8000/api/admin/documents/upload-batch   -F "files=@/path/to/doc1.pdf"   -F "files=@/path/to/doc2.docx"
```

Chỉ tài liệu có trạng thái `READY` mới được CRAG retrieval sử dụng.

## 11. Chat — Agentic CRAG workflow

Chat không dùng Router phân loại trước.

```text
User
 ↓
Agent Runtime
 ↓
Context Manager
 ↓
Agent Core
 ↓
Tool calling
 ├── crag_search
 └── controlled_web_search
 ↓
Citation Validator
 ↓
Response
```

`crag_search`:

```text
Query
  ↓
Chroma + BM25
  ↓
RRF
  ↓
Rerank
  ↓
CRAG Evaluate
  ↓
Evidence
```

Agent có thể tiếp tục gọi `controlled_web_search` nếu evidence nội bộ chưa đủ.

## 12. Test API chat

```bash
curl -X POST http://localhost:8000/api/chat   -H "Content-Type: application/json"   -d '{
    "query": "Điều kiện sử dụng lao động nước ngoài tại Việt Nam là gì?",
    "client_id": "demo_client"
  }'
```

Các endpoint chính:

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/health` | Kiểm tra backend |
| `POST` | `/api/chat` | Chat với Agent |
| `POST` | `/api/chat/stream` | Chat SSE streaming |
| `GET` | `/api/history/{client_id}` | Lịch sử hội thoại |
| `GET` | `/api/memory/{client_id}` | Semantic memory |
| `GET` | `/api/documents` | Tài liệu `READY` |
| `GET` | `/api/admin/documents` | Danh sách tài liệu Admin |
| `GET` | `/api/admin/documents/{id}/chunks` | Xem chunk |
| `POST` | `/api/admin/documents/upload` | Upload một file |
| `POST` | `/api/admin/documents/upload-batch` | Upload nhiều file |

## 13. CLI

Chat qua terminal:

```bash
uv run python main.py
```

Khởi tạo:

```bash
uv run python main.py --init
```

Demo mode:

```bash
uv run python main.py --demo
```

## 14. Evaluation

```bash
uv run python eval/run_eval.py
```

Kết quả phụ thuộc vào corpus, model, provider và threshold hiện tại.

## 15. Build frontend

```bash
cd frontend
pnpm build
```

Frontend dùng Next.js static export và tạo output tại:

```text
frontend/out/
```

Quay về root:

```bash
cd ..
```

## 16. Cập nhật dependencies

### Backend

Đồng bộ đúng `uv.lock`:

```bash
uv sync --python 3.13 --frozen
```

Nếu chủ động thay đổi dependency:

```bash
uv lock
uv sync --python 3.13
```

### Frontend

```bash
cd frontend
pnpm install --frozen-lockfile
```

## 17. Troubleshooting

### `uv: command not found`

```bash
source ~/.bashrc
```

Hoặc cài lại theo [INSTALL.md](INSTALL.md).

### Python không phải 3.13

```bash
uv run python --version
uv sync --python 3.13
```

### `nvm: command not found`

```bash
source ~/.bashrc
command -v nvm
```

### `pnpm: command not found`

```bash
npm install -g pnpm@11.18.0
```

### Ollama không kết nối được

Ubuntu systemd:

```bash
sudo systemctl status ollama
sudo systemctl restart ollama
```

Không có systemd:

```bash
ollama serve
```

### Port 8000 đã được sử dụng

```bash
sudo lsof -i :8000
```

Có thể chạy port khác:

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend không kết nối backend

Kiểm tra:

```bash
curl http://localhost:8000/api/health
```

Nếu frontend và backend chạy trên hai máy khác nhau, cần cấu hình frontend trỏ tới địa chỉ backend thực tế.

### Upload bị lỗi

Kiểm tra log backend và trạng thái document trong Admin UI. Document chưa đạt `READY` sẽ không được CRAG retrieval sử dụng.

## 18. Tài liệu liên quan

- [Installation Guide](INSTALL.md)
- [Workflow](WORKFLOW.md)
- [Knowledge Base](KNOWLEDGE_BASE.md)
- [Technical Documentation](TECHNICAL.md)

```text
INSTALL.md
    ↓
SETUP_AND_RUN.md
    ↓
WORKFLOW.md / KNOWLEDGE_BASE.md
```

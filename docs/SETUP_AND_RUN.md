# Hướng dẫn Kỹ thuật: Cài đặt và Vận hành Hệ thống Legal CRAG Assistant

> **Tài liệu hướng dẫn triển khai toàn diện dự án Trợ lý Tuân thủ & Pháp lý Doanh nghiệp (Legal & Compliance AI Assistant) với Corrective RAG (CRAG) và Session Memory.**

---

## MỤC LỤC

1. [Yêu cầu Hệ thống & Tiên quyết](#1-yêu-cầu-hệ-thống--tiên-quyết)
2. [Cài đặt Môi trường & Gói Thư viện](#2-cài-đặt-môi-trường--gói-thư-viện)
3. [Cấu hình Trung tâm & Biến Môi trường](#3-cấu-hình-trung-tâm--biến-môi-trường)
4. [Bộ Tiền xử lý Dữ liệu Vạn năng (Universal Legal Preprocessor)](#4-bộ-tiền-xử-lý-dữ-liệu-vạn-năng-universal-legal-preprocessor)
5. [Pipeline Nạp Dữ liệu (Ingestion Pipeline)](#5-pipeline-nạp-dữ-liệu-ingestion-pipeline)
6. [Chạy 5 Kịch bản Demo Kiểm chuẩn Bắt buộc](#6-chạy-5-kịch-bản-demo-kiểm-chuẩn-bắt-buộc)
7. [Chạy Giao diện Dòng lệnh Tương tác (CLI Mode)](#7-chạy-giao-diện-dòng-lệnh-tương-tác-cli-mode)
8. [Chạy Bộ Đánh giá Benchmark & Quét lưới Ngưỡng](#8-chạy-bộ-đánh-giá-benchmark--quét-lưới-ngưỡng)
9. [Khởi chạy FastAPI RESTful Gateway (Layer 1 Backend)](#9-khởi-chạy-fastapi-restful-gateway-layer-1-backend)
10. [Nguyên tắc An toàn Memory & Xử lý Sự cố](#10-nguyên-tắc-an-toàn-memory--xử-lý-sự-cố)

---

## 1. Yêu cầu Hệ thống & Tiên quyết

- **Hệ điều hành:** Linux (Ubuntu 22.04 / 24.04 LTS, WSL2), macOS hoặc Windows 11.
- **Python:** Python 3.11 hoặc 3.12 (khuyến nghị 3.12).
- **Bộ quản lý gói:** Khuyến nghị dùng [`uv`](https://github.com/astral-sh/uv) (tốc độ cài đặt cực nhanh) hoặc `pip` tiêu chuẩn.
- **Phần cứng:**
  - Tối thiểu 8GB RAM (16GB RAM nếu chạy local LLM).
  - Không bắt buộc GPU (hệ thống có cơ chế fallback CPU/offline hoàn toàn độc lập cho embedding và reranking). Nếu có GPU NVIDIA, hệ thống tự động tận dụng CUDA.

---

## 2. Cài đặt Môi trường & Gói Thư viện

### Bước 2.1: Kích hoạt Virtual Environment với `uv`
```bash
# Di chuyển vào thư mục dự án
cd /home/ubuntu/ai-agent-crag

# Tạo môi trường ảo
uv venv .venv

# Kích hoạt môi trường ảo
source .venv/bin/activate
```

### Bước 2.2: Cài đặt Dependencies
```bash
uv pip install -r pyproject.toml
```

Các thư viện chính bao gồm:
- **Điều phối Agent:** `langgraph`, `langchain`, `langchain-core`
- **Tầng LLM:** `langchain-openai`, `langchain-groq`, `langchain-ollama`
- **Truy hồi & Vector:** `chromadb`, `langchain-chroma`, `rank-bm25`
- **Xử lý File & PDF:** `pymupdf`, `pillow`, `beautifulsoup4`, `pydantic`
- **API & Web:** `fastapi`, `uvicorn[standard]`, `duckduckgo-search`, `requests`

---

## 3. Cấu hình Trung tâm & Biến Môi trường

Dự án áp dụng mô hình **Pluggable Provider Pattern**, cho phép linh hoạt chuyển đổi giữa các nhà cung cấp LLM mà không cần chỉnh sửa mã nguồn.

Sao chép file cấu hình mẫu:
```bash
cp .env.example .env
```

### Chi tiết các thiết lập trong `.env`:
```ini
# ==============================================================================
# CHỌN NHÀ CUNG CẤP LLM: "groq" | "openai" | "openrouter" | "ollama"
# ==============================================================================
LLM_PROVIDER=groq

# Model tương ứng (danh mục Groq Free Plan cập nhật 2026-09-11):
# - Groq: "qwen/qwen3.8-27b" (khuyến nghị: reasoning, coding, học thuật, tool use, JSON mode),
#   "openai/gpt-oss-120b" (heavy cloud: reasoning mạnh hơn + web/browser/code tools tích hợp),
#   "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound" (agent: web search + code execution)
# - OpenAI: "gpt-4o-mini", "gpt-4o"
# - OpenRouter: "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"
# - Ollama: "qwen3.8:latest" (local fallback tương ứng qwen/qwen3.8-27b), "qwen2.5:14b-instruct"
LLM_MODEL=qwen/qwen3.8-27b
LLM_TEMPERATURE=0.0

# API Keys (điền key của bạn nếu sử dụng cloud provider)
GROQ_API_KEY=gsk_your_groq_api_key_here
OPENAI_API_KEY=sk-your_openai_key_here
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# Provider Endpoints
OLLAMA_BASE_URL=http://localhost:11434
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Ngưỡng quyết định 3 nhánh CRAG (đã tối ưu hóa qua Calibration)
T_LOW=0.40
T_HIGH=0.80
INTERNAL_STRIP_MIN=0.40
```

> **Lưu ý Chế độ Offline/Zero-Key:**  
> Nếu bạn chưa có API Key, hệ thống **vẫn hoạt động hoàn hảo**. Khi không có API Key, LLM Factory sẽ tự động chuyển sang cơ chế tổng hợp câu trả lời xác định (*Deterministic Offline Synthesis*) trích xuất trực tiếp từ các strip có relevance cao nhất kèm theo citation hợp lệ!

---

## 4. Bộ Tiền xử lý Dữ liệu Vạn năng (Universal Legal Preprocessor)

Module `legal/preprocessor.py` chịu trách nhiệm chuẩn hóa mọi tài liệu pháp luật đầu vào vào thư mục `data/`:

### Nguyên tắc hoạt động:
1. **Phát hiện lớp văn bản số (Digital Text):**  
   Với các file PDF có sẵn lớp text (như `data/Bảo hiểm xã hội/41-2024-qh15.pdf`), module trích xuất tự động qua PyMuPDF với tốc độ chỉ ~0.3 giây cho 88 trang.
2. **Xử lý PDF Scan ảnh (Scanned Signed PDF):**  
   Với các file scan ảnh (như `45.signed.pdf`, `59.signed.pdf`), module render các trang thành ảnh PNG lưu tại `data/processed/scanned_pages/`.  
   Khi có API Key, module tự động gọi **Vision LLM** (`gpt-4o-mini`, `llama-3.2-11b-vision-preview`, hoặc `qwen2-vl`) với prompt chuyên dụng số hóa pháp luật, lưu cache tại `data/processed/ocr_cache/` để tái sử dụng vĩnh viễn.
3. **Bóc tách cấu trúc thứ bậc (Legal-aware Chunking):**  
   Tự động tách theo đúng thứ bậc: `Chương -> Điều -> Khoản -> Điểm`.  
   Tạo sẵn các **Legal Strips** có gán nhãn `locator` xác định (ví dụ: `DOC_41_2024_QH15_D2_K1`).

---

## 5. Pipeline Nạp Dữ liệu (Ingestion Pipeline)

Chạy lệnh nạp toàn bộ dữ liệu từ `data/` vào cơ sở dữ liệu SQLite và các hệ thống chỉ mục:

```bash
python ingest.py
```

### Quá trình thực thi bao gồm 4 bước:
1. **Khởi tạo Database SQLite (`app.db`):** Tạo 8 bảng quan hệ và các index tìm kiếm nhanh.
2. **Nạp văn bản vào SQLite:** Đưa toàn bộ metadata văn bản (`legal_documents`) và các điều khoản (`provisions`).
3. **Xây dựng chỉ mục từ khóa BM25:** Tokenize tiếng Việt và lưu file `data/processed/bm25_index.pkl`.
4. **Xây dựng chỉ mục Dense Vector ChromaDB:** Sử dụng vectorizer chuẩn hóa L2 384 chiều (hoặc BGE-M3 khi có Ollama) nạp vào collection `legal_corpus_v1` tại `./chroma`.

---

## 6. Chạy 5 Kịch bản Demo Kiểm chuẩn Bắt buộc

Để nghiệm thu đồ án theo đúng chuẩn mực của **Table 3.2** trong tài liệu hướng dẫn, chạy lệnh sau:

```bash
python main.py --demo
```

### Minh chứng hoạt động của 5 Kịch bản:
- **Test 1 (Correct Case):** Câu hỏi có sẵn trong dữ liệu nội bộ  
  $\to$ Evaluator chấm điểm $\ge T_{high}$  
  $\to$ Action **`CORRECT`**  
  $\to$ Tinh chế Legal Strips  
  $\to$ Sinh câu trả lời kèm citation hợp lệ.
- **Test 2 (Incorrect Case):** Câu hỏi ngoài phạm vi corpus (ví dụ: cấp phép bay drone)  
  $\to$ Evaluator chấm điểm $\le T_{low}$  
  $\to$ Action **`INCORRECT`**  
  $\to$ Viết lại truy vấn  
  $\to$ Kích hoạt Controlled Web Search trên các cổng thông tin nhà nước.
- **Test 3 (Ambiguous Case):** Câu hỏi có căn cứ bộ phận nhưng thiếu chi tiết  
  $\to$ Action **`AMBIGUOUS`**  
  $\to$ Kết hợp tinh lọc nội bộ và tìm kiếm ngoài  
  $\to$ Hợp nhất `merge_evidence` đa nguồn.
- **Test 4 (Database Tool):** “Văn bản số 41/2024/QH15 còn hiệu lực không?”  
  $\to$ Router chuyển sang nhánh **`database`**  
  $\to$ Kiểm tra bảng `legal_documents`  
  $\to$ Trả về ngày hiệu lực `2025-07-01` và trạng thái `Còn hiệu lực`.
- **Test 5 (Citation Failure):** Mô phỏng câu trả lời có source_id bịa đặt (`DOC_FAKE_2099_D999`)  
  $\to$ `validate_citations` phát hiện vi phạm, trả về `ok = False`, chặn câu trả lời ảo giác.

---

## 7. Chạy Giao diện Dòng lệnh Tương tác (CLI Mode)

Khởi động phiên chat tương tác bằng lệnh:

```bash
python main.py
```

### Các tính năng trong CLI:
- **Chat tự nhiên:** Nhập câu hỏi pháp lý bằng tiếng Việt.
- **Theo dõi Execution Trace:** Hiển thị tức thời Route đã chọn (`database` hay `rag`), Action CRAG (`CORRECT`, `AMBIGUOUS`, `INCORRECT`) và số lượng bằng chứng đã bóc tách.
- **Kiểm định Trích dẫn:** Hiển thị danh mục `[Căn cứ trích dẫn]` và cảnh báo nếu có vi phạm.
- **Tự động nhận diện hồ sơ doanh nghiệp:** Ví dụ người dùng nói: *"Tôi phụ trách doanh nghiệp TNHH tại Long An..."* $\to$ Hệ thống tự trích xuất và ghi nhớ `business_type = Công ty TNHH`, `province = Long An`.
- **Lệnh hỗ trợ:**
  - `clear`: Xóa sạch Semantic Memory của phiên làm việc.
  - `exit` hoặc `quit`: Thoát chương trình.

---

## 8. Chạy Bộ Đánh giá Benchmark & Quét lưới Ngưỡng

Để đo lường định lượng và tái lập các bảng số liệu trong **Chương 4**, chạy script:

```bash
python eval/run_eval.py
```

### Quá trình thực thi:
1. **Quét lưới hiệu chuẩn (Grid Search Calibration):**  
   Chạy trên tập `eval/calibration_set.json` (20 câu) qua các cặp ngưỡng $(0.20, 0.60), (0.25, 0.65), ..., (0.40, 0.80)$ để tìm điểm cân bằng tối ưu giữa Action Macro-F1 và hạn chế False Fallback.
2. **Đo kiểm trên Held-Out Test Set (40 câu):**  
   Chạy độc lập trên tập `eval/test_set.json` gồm 5 nhóm câu hỏi:
   - 12 câu Correct (In-corpus)
   - 10 câu Incorrect (Out-of-corpus)
   - 8 câu Ambiguous (Partial evidence)
   - 5 câu Database metadata
   - 5 câu Temporal / Xung đột thời gian
3. **Xuất báo cáo:**  
   Báo cáo tổng hợp tự động lưu tại `eval/benchmark_report.json`.

---

## 9. Khởi chạy FastAPI Backend & Giao diện Next.js Web UI (Layer 1)

Hệ thống cung cấp giao diện Web người dùng bằng **Next.js (TypeScript)** theo đúng đặc tả của đồ án:

### Cách 1: Chạy Full Stack với FastAPI (Khuyến nghị)
Sau khi Next.js được build tĩnh (`npm run build` xuất ra `frontend/out/`), FastAPI Gateway tự động host giao diện trực tiếp tại cổng 8000:
```bash
# Khởi chạy FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Truy cập Web UI:** `http://localhost:8000/`
- **Swagger API Documentation:** `http://localhost:8000/docs`

### Cách 2: Chạy Next.js ở chế độ Development (Hot Reload)
Nếu bạn muốn tùy biến giao diện với tính năng Hot Module Reload (HMR):
```bash
# Terminal 1: Chạy backend FastAPI
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Chạy Next.js Dev Server
cd frontend
npm run dev    # hoặc bun run dev
```
- **Truy cập Next.js Dev Server:** `http://localhost:3000/`
- Giao diện tự động kết nối với API backend tại cổng 8000.

### Tính năng Nổi bật của Giao diện Next.js:
- **Khung chat tương tác:** Render Markdown mượt mà, định dạng nổi bật các thẻ trích dẫn căn cứ pháp luật tím (`[DOC_...]`).
- **Thanh chọn ngày hiệu lực (`as_of_date`):** Cho phép người dùng kiểm tra hiệu lực pháp lý tại bất kỳ mốc thời gian nào.
- **Sidebar:** Quản lý phiên, hiển thị hồ sơ Semantic Memory và danh mục văn bản nội bộ.
- **Bảng Vết Thực Thi (Execution Trace Drawer):** Theo phong cách DeepSeek Harness & Hermes Agent, hiển thị trực quan Route, CRAG Action, Báo cáo trích dẫn, và các thẻ Evidence Cards kèm điểm số relevance.
### Các Endpoints chính:

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| `GET` | `/api/health` | Kiểm tra trạng thái hoạt động của server |
| `POST` | `/api/chat` | Tiếp nhận câu hỏi, chạy đồ thị CRAG, trả về JSON câu trả lời, bằng chứng và trích dẫn |
| `GET` | `/api/documents` | Lấy danh mục các văn bản quy phạm pháp luật đã được nạp |
| `GET` | `/api/history/{client_id}` | Lấy lịch sử hội thoại của một client |
| `GET` | `/api/memory/{client_id}` | Xem hồ sơ Semantic Profile của client |
| `DELETE` | `/api/memory/{client_id}` | Xóa hồ sơ bộ nhớ của client |

### Ví dụ gọi thử nghiệm qua `curl`:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Văn bản số 41/2024/QH15 còn hiệu lực không?",
    "client_id": "browser_client_001"
  }'
```

---

## 10. Nguyên tắc An toàn Memory & Xử lý Sự cố

### 🔒 Nguyên tắc An toàn Bộ nhớ:
1. **Memory Guardrail:** Bối cảnh doanh nghiệp từ Semantic Memory **chỉ được dùng để giải tham chiếu đại từ** (ví dụ: *"công ty tôi"* $\to$ Công ty TNHH tại Long An). **Tuyệt đối không sử dụng thông tin trong memory như một căn cứ pháp lý.**
2. **Cách ly Dữ liệu Tuyệt đối:** Hệ thống đạt chỉ số **Cross-client Contamination = 0**. Dữ liệu của Client A không bao giờ xuất hiện trong phiên truy vấn của Client B.

### 🛠️ Xử lý Sự cố Thường gặp:

- **Lỗi `ModuleNotFoundError: No module named 'agent'`:**  
  *Nguyên nhân:* Chạy file trực tiếp từ thư mục con mà không có project root trong `sys.path`.  
  *Cách khắc phục:* Đã được tích hợp sẵn `sys.path.insert(0, ...)` ở đầu các script, hoặc chạy dạng module: `python -m agent.graph`.
- **Lỗi thiếu API Key của LLM Cloud:**  
  *Khắc phục:* Hệ thống có sẵn bộ suy diễn xác định *Deterministic Offline Synthesis*, bạn hoàn toàn có thể chạy test và demo đầy đủ mà không bắt buộc phải có API Key trả phí.
- **Muốn nạp thêm văn bản mới:**  
  Chỉ cần thả file PDF / DOCX mới vào thư mục `data/`, sau đó chạy lại `python ingest.py`. Bộ tiền xử lý sẽ tự động bóc tách cấu trúc và cập nhật cơ sở dữ liệu.

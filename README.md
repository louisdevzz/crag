# Legal CRAG Assistant — Trợ lý Tuân thủ & Pháp lý Doanh nghiệp

> **Hệ thống AI Agent hỗ trợ tra cứu pháp lý doanh nghiệp Việt Nam với cơ chế tự hiệu chỉnh truy hồi dựa trên Corrective RAG (CRAG) và Quản lý Session Memory 3 tầng.**  
> Triển khai đầy đủ theo đặc tả kỹ thuật 18 bước trong tài liệu Thạc sĩ: `docs/AI_Agent_Corrective_RAG_Memory.pdf`.

---

## 📌 1. Tổng quan Kiến trúc

Hệ thống được thiết kế theo **Kiến trúc 3 Layer Tách biệt**:

- **Layer 1 — Interface & API:** Giao diện dòng lệnh chuyên nghiệp (CLI) và hạ tầng RESTful API (FastAPI) hỗ trợ trả lời, bảng trích dẫn citation xác định, quản lý phiên và hồ sơ client.
- **Layer 2 — Agent Core (ReAct):** Vòng lặp tác tử `agent` ⇄ `tools` trên **LangGraph** — không có node Router phân loại trước; mô hình tự quyết định gọi `crag_search` (Hybrid Retrieval + Rerank + Evaluator Sigmoid + Refine) và/hoặc `controlled_web_search` qua Tool Registry, rồi sinh câu trả lời qua Citation Validator.
- **Layer 3 — Knowledge & Data:** SQLite (`~/.crag/app.db`) quản lý metadata văn bản và memory; ChromaDB (`~/.crag/chroma`) quản lý Dense Vector Index; rank-bm25 quản lý Lexical Index; Reranker tính relevance; Controlled Web Search lọc tên miền công quyền chính thống. Toàn bộ cơ sở dữ liệu và dữ liệu runtime được lưu trữ an toàn tại `~/.crag/` thay vì đặt trong repository.
![Sơ đồ Toàn diện Luồng Hoạt động Legal CRAG Assistant](docs/images/workflow.png)

Hệ thống tuân thủ toàn diện các nguyên lý chuẩn của **[LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)**:
- **State Schema (`AgentState`):** Shared scratchpad truyền dữ liệu giữa các node dạng TypedDict.
- **Ranh giới Formal Graph:** Điểm vào từ `START` và kết thúc tại `END`.
- **Node Functions:** `agent`, `tools`, `cite_validate` (`agent/nodes.py`) — không có node Router riêng, mô hình tự quyết định qua tool-calling.
- **Conditional Edge:** `agent` → có `tool_calls`? → `tools` (lặp lại) : → `cite_validate`.
- **Context Manager, không phải Checkpointer:** Đa lượt hội thoại được lắp ráp tường minh từ SQLite (`agent/context.py`) trước mỗi lần `invoke()` — không dùng `MemorySaver` trong RAM, tránh trạng thái "hai nguồn sự thật" giữa checkpointer và lịch sử bền vững.

---

## 🌟 2. Các Tính năng Đột phá

1. **Bộ Tiền Xử lý Dữ liệu Vạn năng (`legal/preprocessor.py`):**
   - Đọc trực tiếp cả file PDF có lớp văn bản số (digital text) và PDF dạng scan ảnh đóng dấu đỏ.
   - Tự động tích hợp Vision LLM (OpenAI, Groq, OpenRouter, Ollama) chuyển đổi ảnh thành văn bản và lưu đệm tại `data/processed/ocr_cache/`.
   - Bóc tách thứ bậc pháp lý chuẩn mực `Chương -> Điều -> Khoản -> Điểm` (Legal-aware chunking), không gây đứt gãy câu chữ.
2. **Cơ chế Đánh giá 3 Nhánh CRAG:**
   - **Nhánh CORRECT ($Score \ge T_{high}$):** Kích hoạt *Knowledge Refinement* bóc tách các legal strips đạt ngưỡng điểm tối thiểu, loại bỏ nhiễu trước khi đưa vào bộ sinh.
   - **Nhánh INCORRECT ($Score \le T_{low}$):** Nhận diện sự thiếu hụt bằng chứng nội bộ, kích hoạt *Query Rewrite* và tìm kiếm có kiểm soát trên các cổng thông tin pháp luật chính thống (`vbpl.vn`, `chinhphu.vn`, `moj.gov.vn`...).
   - **Nhánh AMBIGUOUS ($T_{low} < Score < T_{high}$):** Tinh lọc tri thức nội bộ kết hợp mở rộng nguồn web có kiểm soát, sau đó hợp nhất (*Evidence Merging*) có ưu tiên độ tin cậy.
3. **Kiểm định Trích dẫn Xác định (Deterministic Citation Validator):**
   - Chặn đứng ảo giác: Mọi khẳng định pháp lý phải có `source_id` tồn tại trong tập bằng chứng thực tế.
   - Kiểm tra hiệu lực thời gian theo ngày tham chiếu `as_of_date` (phát hiện văn bản đã hết hiệu lực).
4. **Agent Runtime với Context Manager (Session, History, Memory):**
   - Phân định rõ: History ngắn hạn từ bảng `messages` (đọc lại qua `agent/context.py` để trả lời câu hỏi nối tiếp), Semantic Profile dài hạn ở bảng `memories`.
   - Kiểm soát nghiêm ngặt bằng danh mục cho phép `ALLOWED_MEMORY_KEYS`.
   - **Cam kết an toàn tuyệt đối:** Memory chỉ dùng để giải tham chiếu thực thể, không bao giờ dùng làm căn cứ pháp lý; đạt chỉ số **Cross-client Contamination = 0**.

---

## 📂 3. Cấu trúc Dự án

```
ai-agent-crag/
├── data/                                # Thư mục chứa dữ liệu văn bản pháp luật thực tế
├── legal/
│   ├── parser.py                        # Phân rã cấu trúc văn bản & legal strips
│   ├── preprocessor.py                  # Pipeline tiền xử lý vạn năng (Text + Vision OCR)
│   ├── temporal.py                      # Đối chiếu hiệu lực thời gian & thứ bậc pháp lý
│   └── citations.py                     # Deterministic Citation Validator
├── retrieval/
│   ├── dense.py                         # Dense Vector Retrieval (ChromaDB)
│   ├── bm25.py                          # Lexical Retrieval (rank-bm25)
│   ├── fusion.py                        # Reciprocal Rank Fusion (RRF k=60)
│   ├── reranker.py                      # Cross-Encoder Reranker Sigmoid & 3-branch routing
│   └── refine.py                        # Knowledge Refinement & Evidence Merging
├── tools/
│   ├── database.py                      # Truy vấn có cấu trúc SQLite
│   └── web_search.py                    # Controlled Web Search lọc tên miền công quyền
├── agent/
│   ├── state.py                         # TypedDict AgentState
│   ├── nodes.py                         # Cài đặt logic toàn bộ nodes
│   └── graph.py                         # Đồ thị LangGraph StateGraph
├── memory/
│   ├── store.py                         # Quản lý 3 tầng Memory & Client Isolation
│   └── extractor.py                     # Trích xuất Semantic Profile qua allow-list
├── eval/
│   ├── calibration_set.json             # 20 câu hiệu chuẩn quét lưới ngưỡng
│   ├── test_set.json                    # 40 câu held-out kiểm thử độc lập
│   ├── metrics.py                       # Các công thức đo đạc Recall, Fallback, Citation
│   └── run_eval.py                      # Script tự động chạy Benchmark
├── api/
│   └── main.py                          # FastAPI RESTful API Gateway
├── config.py                            # Cấu hình trung tâm
├── llm.py                               # LLM Factory đa Provider (Groq, OpenAI, OpenRouter, Ollama)
├── schema.sql                           # Schema 8 bảng SQLite
├── init_system.py                       # Khởi tạo toàn diện hệ thống (~/.crag/, SQLite, Chroma, chẩn đoán)
├── create_db.py                         # Khởi tạo database SQLite tại ~/.crag/app.db
├── ingestion/                           # Pipeline nạp dữ liệu theo giai đoạn (parse/OCR/structure/chunk/embed/index)
├── main.py                              # CLI tương tác & Demo 5 kịch bản bắt buộc (--init, --demo)
└── docs/
    └── SETUP_AND_RUN.md                 # Hướng dẫn chi tiết cài đặt và vận hành
```

---

## 🚀 4. Hướng dẫn Khởi chạy Nhanh

### Bước 1: Chuẩn bị Môi trường
```bash
# Clone repository và di chuyển vào thư mục dự án
cd ai-agent-crag

# Tạo và kích hoạt virtual environment với uv hoặc python venv
uv venv
source .venv/bin/activate

# Cài đặt các thư viện cần thiết
uv pip install -r pyproject.toml
```

### Bước 2: Cấu hình Biến môi trường
Sao chép file mẫu `.env.example` thành `.env`:
```bash
cp .env.example .env
```
*(Nếu muốn dùng LLM bên ngoài như Groq, OpenAI hoặc OpenRouter, hãy điền API key tương ứng vào `.env`)*

### Bước 3: Khởi tạo Hệ thống & Cơ sở Dữ liệu (~/.crag/)
Khởi tạo thư mục làm việc `~/.crag/`, cấu trúc 8 bảng SQLite `~/.crag/app.db`, và kiểm tra toàn diện môi trường:
```bash
python init_system.py
# hoặc: python main.py --init
```
*(Lưu ý: Hệ thống tách biệt hoàn toàn database khỏi repo mã nguồn, lưu trữ tập trung tại `~/.crag/` với chế độ WAL cho hiệu năng truy vấn tối ưu).*

### Bước 4: Tải và Kiểm định Mô hình Thực tế (Embedding & Reranker)
Tải trọng số mô hình từ Hugging Face Hub về bộ đệm cục bộ và kiểm định vector:
```bash
python scripts/pull_models.py
```

### Bước 5: Nạp Văn bản Pháp lý
Khởi động API (`uvicorn api.main:app`) rồi mở trang Admin (`/admin`) để tải lên PDF/DOCX/TXT — pipeline nạp dữ liệu chạy nền theo giai đoạn (xem `docs/WORKFLOW.md` mục 4). Hoặc gọi trực tiếp API:
```bash
curl -X POST http://localhost:8000/api/admin/documents/upload -F "file=@duong/dan/van_ban.pdf"
```

### Bước 6: Chạy 5 Kịch bản Demo Kiểm chuẩn (Table 3.2)
```bash
python main.py --demo
```

### Bước 7: Chạy Trợ lý Tương tác qua Dòng lệnh (CLI Chat)
```bash
python main.py
```

### Bước 8: Chạy Bộ Đánh giá Benchmark Tự động (Chapter 4)
```bash
python eval/run_eval.py
```

### Bước 9: Khởi chạy FastAPI Backend Server & Web UI
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Giao diện Web UI Trực quan:** Mở trình duyệt tại `http://localhost:8000/` (tích hợp khung chat Markdown, sidebar quản lý phiên hội thoại, hồ sơ doanh nghiệp và Bảng Vết Thực Thi Execution Trace Drawer theo phong cách DeepSeek Harness / Hermes Agent).
- **Swagger API Docs:** `http://localhost:8000/docs`
- **Endpoint Chat REST API:** `POST http://localhost:8000/api/chat`
---

## 📊 5. Kết quả Đo kiểm Thực nghiệm (Held-out Test Set 40 câu)

Kết quả đo lường tự động qua `eval/run_eval.py`:

| Nhóm Chỉ số | Tên Chỉ số | Kết quả Đạt được | Ý nghĩa Khoa học |
|---|---|---|---|
| **Retrieval** | Recall@5 | **0.3333** | Tỷ lệ tìm thấy đúng điều khoản trong top-5 |
| **Retrieval** | MRR | **0.2819** | Thứ hạng nghịch đảo của tài liệu liên quan |
| **Routing & Fallback** | Fallback Precision | **1.0000 (100%)** | 100% các lần gọi Web Search đều chính xác |
| **Routing & Fallback** | Fallback Recall | **1.0000 (100%)** | 100% câu hỏi ngoài corpus được phát hiện thành công |
| **Routing & Fallback** | False Fallback Rate | **0.0000 (0%)** | 0% câu hỏi trong corpus bị gọi nhầm ra ngoài |
| **Compliance & Legal** | Citation Accuracy | **0.9750 (97.5%)** | Độ chính xác của source_id trích dẫn |
| **Compliance & Legal** | Citation Coverage | **0.9750 (97.5%)** | Tỷ lệ mệnh đề kết luận có dẫn chứng nguồn |
| **Compliance & Legal** | Legal Temporal Correctness | **0.8000 (80.0%)** | Độ chính xác hiệu lực theo thời gian tham chiếu |
| **Security & Privacy** | Cross-client Contamination | **0.0000 (0%)** | Dữ liệu client A không bao giờ lộ sang client B |

---

## 📖 6. Chi tiết Cài đặt & Vận hành

Xem tài liệu hướng dẫn kỹ thuật chi tiết tại:  
👉 [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md)

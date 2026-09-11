# Legal CRAG Assistant V3 — Trợ lý Tuân thủ & Pháp lý Doanh nghiệp

> **Hệ thống AI Agent hỗ trợ tra cứu pháp lý doanh nghiệp Việt Nam với cơ chế tự hiệu chỉnh truy hồi dựa trên Corrective RAG (CRAG) và Quản lý Session Memory 3 tầng.**  
> Triển khai đầy đủ theo đặc tả kỹ thuật 18 bước trong tài liệu Thạc sĩ: `docs/AI_Agent_Corrective_RAG_Memory.pdf`.

---

## 📌 1. Tổng quan Kiến trúc

Hệ thống được thiết kế theo **Kiến trúc 3 Layer Tách biệt**:

- **Layer 1 — Interface & API:** Giao diện dòng lệnh chuyên nghiệp (CLI) và hạ tầng RESTful API (FastAPI) hỗ trợ trả lời, bảng trích dẫn citation xác định, quản lý phiên và hồ sơ client.
- **Layer 2 — Agent & Correction:** Đồ thị trạng thái **LangGraph** điều phối toàn bộ workflow: Router phân luồng, Retrieval Evaluator chấm điểm relevance chuẩn hóa Sigmoid, 3 nhánh xử lý CRAG cốt lõi, Generator và Citation Validator.
- **Layer 3 — Knowledge & Data:** SQLite (`app.db`) quản lý metadata văn bản và memory; ChromaDB quản lý Dense Vector Index; rank-bm25 quản lý Lexical Index; Reranker tính relevance; Controlled Web Search lọc tên miền công quyền chính thống.
![Sơ đồ Toàn diện Luồng Hoạt động Legal CRAG Assistant V3](docs/images/workflow.png)

Hệ thống tuân thủ toàn diện các nguyên lý chuẩn của **[LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)**:
- **State Schema (`AgentState`):** Shared scratchpad truyền dữ liệu giữa các node dạng TypedDict.
- **Ranh giới Formal Graph:** Điểm vào từ `START` và kết thúc tại `END`.
- **Node Functions:** 11 node biến đổi trạng thái độc lập (`agent/nodes.py`).
- **Conditional Edges:** Rẽ nhánh Router và 3 nhánh tự hiệu chỉnh CRAG (Correct, Ambiguous, Incorrect).
- **Persistence Checkpointing:** Tích hợp `MemorySaver` lưu vết hội thoại đa lượt qua `thread_id`.

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
4. **Quản lý Session Memory 3 Tầng An toàn:**
   - Phân định rõ: Working Memory, Episodic Memory (`query_logs`), Semantic Profile (`client_memories`).
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
├── create_db.py                         # Khởi tạo database app.db
├── ingest.py                            # Pipeline nạp dữ liệu vào SQLite, BM25, Chroma
├── main.py                              # CLI tương tác & Demo 5 kịch bản bắt buộc
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

### Bước 3: Nạp dữ liệu vào Cơ sở Dữ liệu & Vector Store
```bash
python ingest.py
```

### Bước 4: Chạy 5 Kịch bản Demo Kiểm chuẩn (Table 3.2)
```bash
python main.py --demo
```

### Bước 5: Chạy Trợ lý Tương tác qua Dòng lệnh (CLI Chat)
```bash
python main.py
```

### Bước 6: Chạy Bộ Đánh giá Benchmark Tự động (Chapter 4)
```bash
python eval/run_eval.py
```

### Bước 7: Khởi chạy FastAPI Backend Server
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger API Docs: `http://localhost:8000/docs`
- Endpoint Chat: `POST http://localhost:8000/api/chat`

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

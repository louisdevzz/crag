# Sơ đồ và Luồng Hoạt động Toàn diện — Legal CRAG Assistant

> **Tài liệu thuyết minh quy trình điều phối tác tử tự hiệu chỉnh truy hồi Corrective RAG (CRAG) và Quản lý Bộ nhớ Phiên làm việc (Session Memory).**

---

## MỤC LỤC

1. [Tổng quan Kiến trúc 3 Layer](#1-tổng-quan-kiến-trúc-3-layer)
2. [Sơ đồ Luồng Hoạt động Toàn diện (Unified Workflow)](#2-sơ-đồ-luồng-hoạt-động-toàn-diện-unified-workflow)
3. [Thiết kế Chuẩn theo LangGraph Overview](#3-thiết-kế-chuẩn-theo-langgraph-overview)
4. [Thuyết minh Chi tiết Các Giai đoạn Xử lý](#4-thuyết-minh-chi-tiết-các-giai-đoạn-xử-lý)

---

## 1. Tổng quan Kiến trúc 3 Layer

Hệ thống Legal CRAG Assistant tuân thủ nghiêm ngặt nguyên lý phân định ranh giới trách nhiệm (*Separation of Concerns*) giữa 3 tầng chức năng:
- **Layer 1 — Interface & API:** Tiếp nhận yêu cầu từ người dùng qua CLI hoặc FastAPI Gateway (`/api/chat`).
- **Layer 2 — Agent & Correction:** Đồ thị trạng thái **LangGraph** điều phối toàn bộ workflow thông minh.
- **Layer 3 — Knowledge & Data:** SQLite (`app.db`), ChromaDB Vector Store, rank-bm25, và Cổng thông tin pháp luật chính thống.

---

## 2. Sơ đồ Luồng Hoạt động Toàn diện (Unified Workflow)

Toàn bộ quy trình từ lúc tiếp nhận câu hỏi của người dùng, phân luồng điều hướng, truy hồi lai, đánh giá bằng chứng 3 nhánh CRAG, kiểm định trích dẫn đến khi trả về câu trả lời hoàn chỉnh được tích hợp thống nhất trên **một sơ đồ duy nhất**:

![Sơ đồ Toàn diện Luồng Hoạt động Legal CRAG Assistant](images/workflow.png)

---

## 3. Thiết kế Chuẩn theo LangGraph Overview

Kiến trúc tác tử của hệ thống được hiện thực 100% dựa trên các nguyên lý cốt lõi của **[LangGraph Overview Documentation](https://docs.langchain.com/oss/python/langgraph/overview)**:

### 3.1. Sơ đồ Trạng thái (State Schema — `AgentState`)
Theo chuẩn LangGraph, State đóng vai trò là kênh dữ liệu trung tâm (*Shared Scratchpad*):
- Định nghĩa tại `agent/state.py` dưới dạng `TypedDict` có cấu trúc.
- Lưu trữ trạng thái ngữ cảnh (`client_id`, `session_id`, `query`, `as_of_date`, `memory_context`), ứng viên truy hồi (`candidates`), điểm relevance, hành động CRAG (`crag_action`), danh mục bằng chứng (`evidence`), câu trả lời sinh ra (`generation`) và báo cáo trích dẫn (`citation_report`).

### 3.2. Ranh giới Đồ thị Chính thức (`START` và `END`)
Tuân thủ chuẩn LangGraph mới nhất, đồ thị sử dụng các nút ranh giới chính thức:
- `from langgraph.graph import START, END, StateGraph`
- Điểm vào: `g.add_edge(START, "router")`
- Điểm kết thúc: `g.add_edge("cite_validate", END)`

### 3.3. Các Node Biến đổi Độc lập (Pure Node Functions)
Cài đặt tại `agent/nodes.py`, mỗi node là một hàm Python nhận `(state: AgentState)` và trả về dictionary cập nhật trạng thái mà không làm thay đổi các trường dữ liệu khác:
- `route_question`: Router phân loại câu hỏi (`database`, `rag`, `general`).
- `query_db`: Truy vấn dữ liệu có cấu trúc SQLite.
- `hybrid_retrieve`: Truy hồi lai Dense + Lexical BM25 + RRF Fusion.
- `evaluate_retrieval`: Cross-Encoder Reranker chấm điểm relevance Sigmoid $[0, 1]$.
- `refine_internal_node`: Tinh lọc tri thức nội bộ thành các legal strips.
- `rewrite_query_node`: Viết lại câu truy vấn tìm kiếm chuyên sâu.
- `web_search_node`: Tìm kiếm nguồn web công quyền cho phép.
- `select_external_node`: Bóc tách và chọn lọc bằng chứng từ web.
- `merge_evidence_node`: Hợp nhất bằng chứng đa nguồn theo thứ tự ưu tiên.
- `generate_answer`: Sinh câu trả lời theo khuôn mẫu JSON nghiêm ngặt.
- `validate_citations_node`: Kiểm tra tính xác thực và hiệu lực thời gian của trích dẫn.

### 3.4. Các Cạnh Điều Kiện (Conditional Edges & 3-Branch CRAG)
Cài đặt tại `agent/graph.py` điều khiển luồng rẽ nhánh linh hoạt:
- Rẽ nhánh Router: `router` $\to$ `{"database": "db", "rag": "retrieve", "general": "generate"}`.
- Rẽ 3 nhánh CRAG sau Evaluator: `evaluate` $\to$ `{"CORRECT": "refine", "AMBIGUOUS": "refine", "INCORRECT": "rewrite"}`.
- Rẽ nhánh sau Refinement: `refine` $\to$ `{"generate": "generate", "rewrite": "rewrite"}`.
- Rẽ nhánh sau Web Selection: `select_web` $\to$ `{"merge": "merge", "generate": "generate"}`.

### 3.5. Cơ chế Lưu vết & Trí nhớ Phiên (Persistence & Checkpointing)
Hệ thống biên dịch đồ thị với **Checkpointer** chính thức của LangGraph:
```python
from langgraph.checkpoint.memory import MemorySaver

app = g.compile(checkpointer=MemorySaver())
```
Khi thực thi mỗi turn, hệ thống truyền định danh luồng hội thoại theo chuẩn LangGraph:
```python
config = {"configurable": {"thread_id": session_id}}
result = app.invoke(state_input, config=config)
```
Cơ chế này đảm bảo đồ thị có khả năng duy trì trạng thái ngữ cảnh qua nhiều lượt tương tác (*multi-turn dialog*) và sẵn sàng hỗ trợ các tính năng cao cấp như Time-travel hoặc Human-in-the-loop.

---
## 4. Thuyết minh Các Giai đoạn Xử lý trong Luồng

Quy trình hoạt động trên sơ đồ được chia thành 6 giai đoạn logic:

### Giai đoạn 1: Tiếp nhận Yêu cầu & Nhận diện Phiên
- **Người dùng / Trình duyệt:** Gửi câu hỏi pháp lý kèm mã định danh ẩn danh (`client_id`) và phiên (`session_id`).
- **Cổng API Gateway (FastAPI):** Tiếp nhận yêu cầu, bảo đảm tính độc lập của từng client.

### Giai đoạn 2: Quản lý Bộ nhớ Phiên (Session Memory)
- **Cơ chế Allow-List:** Tự động trích xuất các thuộc tính hồ sơ doanh nghiệp bền vững (`business_type`, `industry`, `province`...).
- **Nguyên tắc Memory Guardrail:** Bối cảnh doanh nghiệp chỉ dùng để giải nghĩa đại từ (ví dụ: *"công ty tôi"* $\to$ Công ty TNHH tại Long An), tuyệt đối không bao giờ dùng làm căn cứ pháp lý.
- **Cam kết Cách ly:** Đạt chỉ số an toàn **Cross-client Contamination = 0** (dữ liệu client A không bao giờ rò rỉ sang client B).

### Giai đoạn 3: Bộ Điều hướng Thông minh (Query Router)
Phân tích ngữ nghĩa câu hỏi để chuyển nhánh tối ưu:
- **Nhánh Tra cứu CSDL (DB Tool):** Khi câu hỏi hỏi về số hiệu văn bản, ngày ban hành, hoặc tình trạng hiệu lực (ví dụ: *"Văn bản số 41/2024/QH15 còn hiệu lực không?"*) $\to$ Truy vấn trực tiếp các bảng quan hệ SQLite để trả lời ngay lập tức.
- **Nhánh Tra cứu Nội dung (CRAG Pipeline):** Đối với mọi câu hỏi hỏi về quy định, điều kiện, quyền và nghĩa vụ $\to$ Kích hoạt chu trình truy hồi và tự hiệu chỉnh CRAG.

### Giai đoạn 4: Truy hồi Lai (Hybrid Retrieval) & Đánh giá Bằng chứng (Evaluator)
1. **Truy hồi song song:**
   - **Dense Vector:** Tìm kiếm ngữ nghĩa trên ChromaDB với vector embeddings.
   - **Lexical BM25:** Tìm kiếm từ khóa chính xác (`rank-bm25`) bắt trọn số Điều, Khoản.
2. **Hợp nhất Xếp hạng (RRF):** Kết hợp hai danh sách ứng viên theo giải thuật *Reciprocal Rank Fusion* ($k=60$) để tạo ra Top-20 ứng viên tốt nhất.
3. **Đánh giá Bằng chứng (Cross-Encoder Sigmoid):**
   - Mô hình Reranker tính điểm liên quan chuẩn hóa Sigmoid trong đoạn $[0.0, 1.0]$.
   - Quyết định hành động dựa trên 2 ngưỡng tối ưu đã được hiệu chuẩn:
     - $Score \ge T_{high} = 0.80 \;\longrightarrow\;$ **Nhánh ĐỦ BẰNG CHỨNG (CORRECT)**
     - $0.40 \le Score < 0.80 \;\longrightarrow\;$ **Nhánh BẰNG CHỨNG MỘT PHẦN (AMBIGUOUS)**
     - $Score \le T_{low} = 0.40 \;\longrightarrow\;$ **Nhánh THIẾU BẰNG CHỨNG (INCORRECT)**

### Giai đoạn 5: Cơ chế Tự Hiệu chỉnh 3 Nhánh CRAG
- 🟢 **Nhánh CORRECT (Đủ bằng chứng):**
  Kích hoạt *Knowledge Refinement* phân tách các đoạn dài thành từng *Legal Strip* (Khoản/Điểm cụ thể), lọc bỏ nhiễu và chuyển thẳng sang Bộ sinh lời giải.
- 🟡 **Nhánh AMBIGUOUS (Một phần bằng chứng):**
  Vừa tinh lọc các legal strips nội bộ, vừa kích hoạt *Query Rewrite* để tìm kiếm mở rộng có kiểm soát trên các cổng thông tin pháp luật chính thống (`vbpl.vn`, `chinhphu.vn`, `moj.gov.vn`...). Sau đó, cơ chế *Evidence Merging* hợp nhất đa nguồn với ưu tiên: **Nguồn nội bộ chính thống > Nguồn bổ trợ ngoài web**.
- 🔴 **Nhánh INCORRECT (Thiếu bằng chứng):**
  Nhận diện corpus nội bộ không có dữ liệu, loại bỏ tài liệu không liên quan, viết lại truy vấn và tìm kiếm trên các cổng thông tin pháp luật chính thống.

### Giai đoạn 6: Sinh Lời Giải & Kiểm Định Trích Dẫn (Citation Validator)
1. **Bộ Sinh Lời Giải (Structured Generator):**
   - Áp dụng Prompt ràng buộc nghiêm ngặt: Chỉ kết luận khi có bằng chứng.
   - Trả về đúng định dạng JSON Schema: `answer`, danh sách `claims` kèm `source_ids`, và cờ `abstain`.
2. **Kiểm định Trích dẫn Xác định (Deterministic Citation Validator):**
   - Kiểm tra xác thực: Mọi `source_id` được trích dẫn phải tồn tại trong tập bằng chứng thực tế.
   - Kiểm tra hiệu lực thời gian: Đối chiếu ngày tham chiếu `as_of_date` với ngày hết hiệu lực của văn bản.
   - Nếu phát hiện vi phạm hoặc nguồn bịa đặt: Lập tức chặn câu trả lời hoặc phát cảnh báo trích dẫn sai.


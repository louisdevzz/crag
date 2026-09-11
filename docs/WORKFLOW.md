# Sơ đồ và Luồng Hoạt động Toàn diện — Legal CRAG Assistant V3

> **Tài liệu thuyết minh quy trình điều phối tác tử tự hiệu chỉnh truy hồi Corrective RAG (CRAG) và Quản lý Bộ nhớ Phiên làm việc (Session Memory).**

---

## 1. Sơ đồ Luồng Hoạt động Toàn diện (Unified Architecture Workflow)

Toàn bộ quy trình từ lúc tiếp nhận câu hỏi của người dùng, phân luồng điều hướng, truy hồi lai, đánh giá bằng chứng 3 nhánh CRAG, kiểm định trích dẫn đến khi trả về câu trả lời hoàn chỉnh được tích hợp thống nhất trên **một sơ đồ duy nhất**:

![Sơ đồ Toàn diện Luồng Hoạt động Legal CRAG Assistant V3](images/workflow.png)

---

## 2. Thuyết minh Các Giai đoạn Xử lý trong Luồng

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

---

## 3. Lệnh Tự động Render Lại Hình ảnh Sơ đồ

Sơ đồ `docs/images/workflow.png` và `docs/images/workflow.svg` được tạo từ file định nghĩa `docs/workflow.mmd`.  
Khi cần chỉnh sửa hoặc render lại ảnh với nền trắng chuẩn, chạy lệnh:

```bash
.venv/bin/python scripts/render_mermaid.py docs/workflow.mmd --output-dir docs/images
```

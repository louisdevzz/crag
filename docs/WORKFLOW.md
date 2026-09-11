# Tài liệu Luồng Hoạt động Hệ thống (Workflow Architecture)

> **Mô tả chi tiết nguyên lý vận hành, kiến trúc 3 tầng, quy trình tự hiệu chỉnh truy hồi Corrective RAG (CRAG) 3 nhánh và cơ chế quản lý Session Memory có kiểm soát.**

---

## MỤC LỤC

1. [Tổng quan Kiến trúc 3 Layer](#1-tổng-quan-kiến-trúc-3-layer)
2. [Sơ đồ Kiến trúc 3 Layer (Diagram 1)](#2-sơ-đồ-kiến-trúc-3-layer-diagram-1)
3. [Luồng Hoạt động Cốt lõi CRAG 3 Nhánh (Diagram 2)](#3-luồng-hoạt-động-cốt-lõi-crag-3-nhánh-diagram-2)
4. [Phân tích Chi tiết Từng Node Xử lý](#4-phân-tích-chi-tiết-từng-node-xử-lý)
5. [Cơ chế Session Memory & Cách ly Tuyệt đối (Diagram 3)](#5-cơ-chế-session-memory--cách-ly-tuyệt-đối-diagram-3)
6. [Tái lập Hình ảnh Sơ đồ từ Mermaid](#6-tái-lập-hình-ảnh-sơ-đồ-từ-mermaid)

---

## 1. Tổng quan Kiến trúc 3 Layer

Hệ thống Legal CRAG Assistant V3 tuân thủ nghiêm ngặt nguyên lý phân định ranh giới trách nhiệm (*Separation of Concerns*) giữa 3 tầng chức năng:

- **Layer 1 — Interface & API:**  
  Tiếp nhận yêu cầu từ người dùng qua CLI hoặc FastAPI Gateway. Phụ trách quản lý định danh ẩn danh (`client_id`, `session_id`) và trả về kết quả kèm bảng trích dẫn minh bạch.
- **Layer 2 — Agent & Correction (LangGraph):**  
  Bộ não điều phối luồng thực thi: Phân luồng câu hỏi, truy hồi lai, chấm điểm bằng chứng bằng mô hình độc lập (*Retrieval Evaluator*), rẽ 3 nhánh xử lý thích ứng (*Knowledge Refinement, Query Rewrite, Controlled Web Search, Evidence Merging*), sinh câu trả lời có cấu trúc và kiểm định trích dẫn xác định (*Citation Validator*).
- **Layer 3 — Knowledge & Data:**  
  Hạ tầng dữ liệu bền vững gồm SQLite (`app.db`) quản lý văn bản, điều khoản và lịch sử; ChromaDB lưu trữ Dense Vector Index; rank-bm25 lưu trữ Lexical Index; và bộ lọc tên miền công quyền chính thống (`vbpl.vn`, `chinhphu.vn`...).

---

## 2. Sơ đồ Kiến trúc 3 Layer (Diagram 1)

![3-Layer Architecture](images/arch_3layer.png)

```mermaid
%% arch_3layer
graph TB
    subgraph L1 ["LAYER 1 — INTERFACE & API GATEWAY"]
        UI["🖥️ Next.js Web Frontend<br/>(TypeScript / localStorage)"]
        CLI["💻 Interactive CLI Chat<br/>(main.py --demo)"]
        API["⚡ FastAPI RESTful API Gateway<br/>(/api/chat, /api/memory, /api/documents)"]
    end

    subgraph L2 ["LAYER 2 — AGENT & CORRECTION ORCHESTRATOR (LangGraph)"]
        ROUTER["🧭 Query Router<br/>(database vs rag vs general)"]
        HYBRID["🔍 Hybrid Retrieval<br/>(Dense + Lexical BM25 + RRF)"]
        EVAL["⚖️ Retrieval Evaluator<br/>(Cross-Encoder Sigmoid Relevance)"]
        REFINE["✂️ Knowledge Refinement<br/>(Decompose into Legal Strips)"]
        REWRITE["✏️ Query Rewrite Engine<br/>(Optimized Legal Search Query)"]
        WEB["🌐 Controlled Web Search<br/>(Official Legal Portals Allow-list)"]
        MERGE["🔗 Evidence Merging<br/>(Internal Strip Priority > Web)"]
        GEN["📝 Structured Generator<br/>(Strict JSON Schema + Citations)"]
        CITE["🛡️ Deterministic Citation Validator<br/>(Verify source_id & Temporal Validity)"]
    end

    subgraph L3 ["LAYER 3 — KNOWLEDGE & DATA STORAGE"]
        SQL["🗄️ SQLite Database (app.db)<br/>• legal_documents<br/>• provisions<br/>• client_memories<br/>• query_logs"]
        CHROMA["🧠 Chroma Vector Database<br/>• Dense Embeddings (384-dim / BGE-M3)<br/>• Collection: legal_corpus_v1"]
        BM25["📚 BM25 Lexical Store<br/>• rank-bm25 Token Index<br/>• Exact Article/Clause Match"]
        GOV_WEB["🏛️ Official Portals Allow-List<br/>• vbpl.vn<br/>• vanban.chinhphu.vn<br/>• moj.gov.vn<br/>• thuvienphapluat.vn"]
    end

    UI --> API
    CLI --> L2
    API --> ROUTER

    ROUTER -->|Metadata Query| SQL
    ROUTER -->|Legal QA| HYBRID

    HYBRID --> CHROMA
    HYBRID --> BM25
    HYBRID --> EVAL

    EVAL -->|Correct| REFINE
    EVAL -->|Ambiguous| REFINE
    EVAL -->|Ambiguous| REWRITE
    EVAL -->|Incorrect| REWRITE

    REWRITE --> WEB
    WEB --> GOV_WEB
    REFINE --> MERGE
    WEB --> MERGE
    REFINE --> GEN
    MERGE --> GEN
    WEB --> GEN

    GEN --> CITE
    CITE --> SQL
    CITE --> API

    classDef l1Style fill:#E0F2FE,stroke:#0284C7,stroke-width:2px,color:#0369A1;
    classDef l2Style fill:#F3E8FF,stroke:#9333EA,stroke-width:2px,color:#6B21A8;
    classDef l3Style fill:#ECFDF5,stroke:#059669,stroke-width:2px,color:#047857;

    class UI,CLI,API l1Style;
    class ROUTER,HYBRID,EVAL,REFINE,REWRITE,WEB,MERGE,GEN,CITE l2Style;
    class SQL,CHROMA,BM25,GOV_WEB l3Style;
```

---

## 3. Luồng Hoạt động Cốt lõi CRAG 3 Nhánh (Diagram 2)

Trọng tâm của kỹ thuật Corrective RAG là **không bao giờ tin tưởng tuyệt đối vào kết quả truy hồi ban đầu**. Thay vào đó, bộ đánh giá độc lập phân loại tập ứng viên thành 3 trạng thái điều kiện:

- 🟢 **CORRECT ($Score \ge T_{high} = 0.80$):** Bằng chứng nội bộ đầy đủ $\to$ Kích hoạt *Knowledge Refinement* bóc tách các legal strips cụ thể $\to$ Đưa vào Generator.
- 🟡 **AMBIGUOUS ($T_{low} \le Score < T_{high}$):** Bằng chứng nội bộ có một phần $\to$ Vừa tinh lọc nội bộ, vừa viết lại truy vấn để tìm kiếm bổ sung trên web $\to$ *Evidence Merging* hợp nhất đa nguồn có ưu tiên.
- 🔴 **INCORRECT ($Score \le T_{low} = 0.40$):** Bằng chứng nội bộ thiếu hụt $\to$ Loại bỏ tài liệu rác $\to$ Viết lại truy vấn $\to$ Gọi Controlled Web Search cổng thông tin nhà nước.

![CRAG 3-Branch Workflow](images/crag_workflow.png)

```mermaid
%% crag_workflow
flowchart TD
    START([🚀 User Legal Query]) --> ROUTER{🧭 Router Phân loại}

    %% Branch Database
    ROUTER -->|Câu hỏi tra cứu số hiệu / hiệu lực| DB[🗄️ Query DB Tool]
    DB --> CITE_VAL

    %% Branch RAG
    ROUTER -->|Câu hỏi tra cứu nội dung quy định| HYBRID[🔍 Hybrid Retrieval<br/>Dense BGE-M3 + Lexical BM25]
    HYBRID --> RRF[⚡ RRF Fusion k=60<br/>Top-20 Candidates]
    RRF --> EVAL[⚖️ Retrieval Evaluator<br/>Cross-Encoder Sigmoid Score]

    %% 3-Branch Decision
    EVAL -->|Score >= T_high 0.80| BR_CORRECT[🟢 Nhánh CORRECT<br/>Bằng chứng nội bộ đầy đủ]
    EVAL -->|T_low <= Score < T_high| BR_AMBIGUOUS[🟡 Nhánh AMBIGUOUS<br/>Bằng chứng chưa đủ / một phần]
    EVAL -->|Score <= T_low 0.40| BR_INCORRECT[🔴 Nhánh INCORRECT<br/>Corpus nội bộ thiếu hụt]

    %% Correct Branch
    BR_CORRECT --> REFINE[✂️ Knowledge Refinement<br/>Chia nhỏ thành Legal Strips<br/>Lọc Score >= 0.40]
    REFINE --> GEN[📝 Structured Generator<br/>JSON Schema: answer + claims + abstain]

    %% Ambiguous Branch
    BR_AMBIGUOUS --> REFINE_AMB[✂️ Refine Internal Strips]
    BR_AMBIGUOUS --> REWRITE_AMB[✏️ Query Rewrite]
    REWRITE_AMB --> WEB_AMB[🌐 Controlled Web Search<br/>vbpl.vn, chinhphu.vn...]
    WEB_AMB --> SELECT_WEB_AMB[🔍 Select External Strips]
    REFINE_AMB --> MERGE[🔗 Evidence Merging<br/>Ưu tiên: Nội bộ > Nguồn ngoài]
    SELECT_WEB_AMB --> MERGE
    MERGE --> GEN

    %% Incorrect Branch
    BR_INCORRECT --> REWRITE_INC[✏️ Query Rewrite]
    REWRITE_INC --> WEB_INC[🌐 Controlled Web Search]
    WEB_INC --> SELECT_WEB_INC[🔍 Select External Strips]
    SELECT_WEB_INC --> GEN

    %% Generation and Validation
    GEN --> CITE_VAL{🛡️ Citation Validator<br/>Kiểm tra xác định}
    CITE_VAL -->|source_id tồn tại & Còn hiệu lực| OK([✅ Trả lời Thành công kèm Citations])
    CITE_VAL -->|Vi phạm / Bịa đặt / Hết hiệu lực| BLOCK([⚠️ Báo lỗi Trích dẫn / Cảnh báo])

    classDef startStyle fill:#3B82F6,stroke:#1D4ED8,stroke-width:2px,color:#FFFFFF;
    classDef routerStyle fill:#8B5CF6,stroke:#6D28D9,stroke-width:2px,color:#FFFFFF;
    classDef correctStyle fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#15803D;
    classDef ambStyle fill:#FEF3C7,stroke:#D97706,stroke-width:2px,color:#B45309;
    classDef incStyle fill:#FEE2E2,stroke:#DC2626,stroke-width:2px,color:#B91C1C;
    classDef genStyle fill:#F3E8FF,stroke:#7E22CE,stroke-width:2px,color:#581C87;
    classDef valStyle fill:#FCE7F3,stroke:#DB2777,stroke-width:2px,color:#9D174D;
    classDef endStyle fill:#059669,stroke:#047857,stroke-width:2px,color:#FFFFFF;

    class START startStyle;
    class ROUTER routerStyle;
    class BR_CORRECT,REFINE correctStyle;
    class BR_AMBIGUOUS,REFINE_AMB,REWRITE_AMB,WEB_AMB,SELECT_WEB_AMB,MERGE ambStyle;
    class BR_INCORRECT,REWRITE_INC,WEB_INC,SELECT_WEB_INC incStyle;
    class GEN genStyle;
    class CITE_VAL,BLOCK valStyle;
    class OK endStyle;
```

---

## 4. Phân tích Chi tiết Từng Node Xử lý

| Tên Node | Module thực thi | Chức năng chi tiết và Quy tắc vận hành |
|---|---|---|
| `router` | `agent/nodes.py` | Kiểm tra regex số hiệu văn bản và từ khóa hiệu lực. Nếu tra cứu hiệu lực/ngày ban hành $\to$ chuyển `db`; nếu chào hỏi ngắn $\to$ `general`; còn lại $\to$ `rag`. |
| `query_db` | `tools/database.py` | Truy vấn trực tiếp các bảng quan hệ SQLite (`legal_documents`, `legal_relations`) để lấy tình trạng hiệu lực và văn bản sửa đổi/bổ sung/thay thế. |
| `hybrid_retrieve` | `retrieval/` | Chạy đồng thời `dense_retrieve` (Chroma vector) và `bm25_retrieve` (rank-bm25), sau đó kết hợp bằng giải thuật Reciprocal Rank Fusion ($k=60$) tạo danh sách Top-20. |
| `evaluate_retrieval` | `retrieval/reranker.py` | Sử dụng Cross-Encoder tính relevance score chuẩn hóa hàm Sigmoid vào $[0, 1]$. So sánh điểm tối đa với hai ngưỡng $(T_{low}=0.40, T_{high}=0.80)$ để rẽ 3 nhánh. |
| `refine_internal_node` | `retrieval/refine.py` | Bóc tách từng Điều/Khoản thành các *Legal Strips* độc lập, chấm lại điểm liên quan và chỉ giữ lại các strip có điểm $\ge \text{INTERNAL\_STRIP\_MIN} = 0.40$. |
| `rewrite_query_node` | `agent/nodes.py` | Loại bỏ từ ngữ thừa trong câu hỏi tự nhiên (như *"cho tôi hỏi"*, *"theo quy định hiện hành thì"*...), chuẩn hóa thành từ khóa chuyên ngành để tìm kiếm web chính xác. |
| `web_search_node` | `tools/web_search.py` | Thực thi tìm kiếm trên DuckDuckGo với bộ lọc tên miền công quyền cho phép (`vbpl.vn`, `vanban.chinhphu.vn`, `moj.gov.vn`, `chinhphu.vn`, `thuvienphapluat.vn`). |
| `select_external_node` | `retrieval/refine.py` | Tải trang hoặc trích xuất snippet từ web, phân tách thành các legal strips và chấm điểm chọn lọc các strip đạt chuẩn. |
| `merge_evidence_node` | `retrieval/refine.py` | Hợp nhất danh sách bằng chứng nội bộ và ngoài web, khử trùng lặp theo locator, áp dụng độ ưu tiên: **Nội bộ chính thống (priority=2) > Nguồn bổ trợ ngoài (priority=1)**. |
| `generate_answer` | `agent/nodes.py` | Sử dụng prompt ràng buộc nghiêm ngặt (Listing 3.14), ép định dạng JSON Schema gồm `answer`, `claims` có gắn kèm `source_ids`, và cờ `abstain` khi không đủ căn cứ. |
| `validate_citations_node`| `legal/citations.py` | Đối chiếu từng `source_id` được trích dẫn với tập bằng chứng thực tế; kiểm tra văn bản có còn hiệu lực tại ngày tham chiếu `as_of_date` hay không. |

---

## 5. Cơ chế Session Memory & Cách ly Tuyệt đối (Diagram 3)

### 3 Cấp độ Memory:
1. **Tier 1 — Working Memory (`AgentState`):** Duy trì trong RAM suốt 1 turn truy vấn.
2. **Tier 2 — Episodic Memory (`query_logs` SQLite):** Lưu vết tuần tự mọi câu hỏi, câu trả lời, route và action đã chọn.
3. **Tier 3 — Semantic Profile (`client_memories` SQLite):** Ghi nhớ thuộc tính bền vững của doanh nghiệp chỉ qua 5 thuộc tính được phép trong `ALLOWED_MEMORY_KEYS`:
   - `business_type`: Loại hình (TNHH, Cổ phần...)
   - `industry`: Ngành nghề (Xây dựng, Bán lẻ...)
   - `province`: Địa bàn (Hà Nội, TP.HCM, Long An...)
   - `frequent_topic`: Lĩnh vực hay hỏi (Lao động, Hợp đồng...)
   - `preferred_answer`: Phong cách mong muốn (Ngắn gọn, Chi tiết...)

![Session Memory Architecture](images/memory_isolation.png)

```mermaid
%% memory_isolation
graph TB
    subgraph CLIENT_A ["CLIENT A (Browser 1 - localStorage)"]
        CA_ID["client_id: client_alpha"]
        CA_ACT["'Doanh nghiệp TNHH tại Long An, muốn hỏi hợp đồng thử việc'"]
    end

    subgraph CLIENT_B ["CLIENT B (Browser 2 - Isolated)"]
        CB_ID["client_id: client_beta"]
        CB_ACT["'Công ty tôi cần lưu ý gì khi ký hợp đồng?'"]
    end

    subgraph BACKEND ["FASTAPI GATEWAY & AGENT CORE"]
        GATEWAY["🚪 FastAPI Gateway<br/>(Extract client_id & session_id)"]
        EXTRACTOR["⚙️ Memory Extractor<br/>(Enforce ALLOWED_MEMORY_KEYS)"]
        GUARD["🛡️ Memory Guardrail<br/>Bối cảnh Client != Căn cứ Pháp lý"]
        CORE["🤖 LangGraph CRAG Core<br/>(Bắt buộc truy hồi văn bản hiện hành)"]
    end

    subgraph STORAGE ["SQLITE APP.DB (STRICT ISOLATION)"]
        subgraph MEM_A ["Partition Client Alpha"]
            A_PROF["client_memories (Alpha)<br/>• business_type: TNHH<br/>• province: Long An"]
            A_LOGS["query_logs (Alpha)"]
        end
        subgraph MEM_B ["Partition Client Beta"]
            B_PROF["client_memories (Beta)<br/>(RỖNG / KHÔNG CÓ DỮ LIỆU)"]
            B_LOGS["query_logs (Beta)"]
        end
    end

    CA_ID --> GATEWAY
    CA_ACT --> GATEWAY
    CB_ID -.->|Không truy cập dữ liệu Alpha| GATEWAY

    GATEWAY --> EXTRACTOR
    EXTRACTOR -->|Ghi hồ sơ Alpha| A_PROF
    EXTRACTOR --> GUARD

    GUARD -->|Chỉ dùng giải nghĩa đại từ| CORE
    CORE --> A_LOGS

    B_PROF -.->|Cross-client Contamination = 0| GATEWAY

    classDef clientStyle fill:#EFF6FF,stroke:#3B82F6,stroke-width:2px,color:#1E40AF;
    classDef gateStyle fill:#F5F3FF,stroke:#8B5CF6,stroke-width:2px,color:#5B21B6;
    classDef storeA fill:#ECFDF5,stroke:#10B981,stroke-width:2px,color:#065F46;
    classDef storeB fill:#FEF2F2,stroke:#EF4444,stroke-width:2px,color:#991B1B;

    class CA_ID,CA_ACT,CB_ID,CB_ACT clientStyle;
    class GATEWAY,EXTRACTOR,GUARD,CORE gateStyle;
    class A_PROF,A_LOGS storeA;
    class B_PROF,B_LOGS storeB;
```

---

## 6. Tái lập Hình ảnh Sơ đồ từ Mermaid

Hệ thống đã xây dựng sẵn công cụ `scripts/render_mermaid.py` để tự động render toàn bộ sơ đồ Mermaid trong tài liệu này thành các file ảnh PNG và SVG chất lượng cao:

```bash
# Render toàn bộ sơ đồ trong WORKFLOW.md sang thư mục docs/images/
python scripts/render_mermaid.py docs/WORKFLOW.md --output-dir docs/images
```

Các file ảnh kết quả sẽ được tạo tại:
- `docs/images/arch_3layer.png` & `arch_3layer.svg`
- `docs/images/crag_workflow.png` & `crag_workflow.svg`
- `docs/images/memory_isolation.png` & `memory_isolation.svg`

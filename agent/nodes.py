"""LangGraph Node Implementations for Legal CRAG Assistant V3."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from agent.state import AgentState
from config import T_HIGH, T_LOW
from legal.citations import validate_citations
from llm import get_chat_model
from retrieval.bm25 import bm25_retrieve
from retrieval.dense import dense_retrieve
from retrieval.fusion import rrf_merge
from retrieval.refine import merge_evidence, refine_external, refine_internal
from retrieval.reranker import decide_crag_action, rerank
from agent.router import get_semantic_router
from retrieval.rewriter import get_query_rewriter
from tools.registry import get_tool_registry

def route_question(state: AgentState) -> Dict[str, Any]:
    """Route user query dynamically via SemanticRouter (Intent Classification)."""
    query = state.get("query", "").strip()
    router = get_semantic_router()
    decision = router.route(query)
    return {
        "route": decision.route,
        "trace_meta": {
            "routing_reasoning": decision.reasoning,
            "detected_docs": decision.detected_document_numbers,
        }
    }

def query_db(state: AgentState) -> Dict[str, Any]:
    """Execute database query tool via ToolRegistry."""
    query = state.get("query", "")
    as_of_date = state.get("as_of_date")
    tool_res = get_tool_registry().execute("database_query", query=query, as_of_date=as_of_date)
    result = tool_res.data if tool_res.success and tool_res.data else {}
    docs = result.get("found_documents", [])
    if docs:
        doc = docs[0]
        status_vi = "Còn hiệu lực" if doc.get("is_effective_now", True) else "Đã hết hiệu lực"
        eff_from = doc.get("effective_from") or "Chưa rõ"
        eff_to = doc.get("effective_to") or "Đang áp dụng"
        authority = doc.get("issuing_authority") or "Cơ quan có thẩm quyền"

        answer_text = (
            f"Văn bản **{doc.get('document_number')}** - *{doc.get('title')}* "
            f"do {authority} ban hành. "
            f"Ngày có hiệu lực: {eff_from}. Trạng thái hiệu lực: **{status_vi}**."
        )

        relations = doc.get("relations", [])
        if relations:
            rel_texts = []
            for r in relations:
                rel_type = r.get("relation_type", "")
                if rel_type == "replaces":
                    rel_texts.append(f"Thay thế cho {r.get('target_number')}")
                elif rel_type == "guides":
                    rel_texts.append(f"Hướng dẫn cho {r.get('target_number')}")
            if rel_texts:
                answer_text += " Quan hệ văn bản: " + "; ".join(rel_texts) + "."

        generation = {
            "answer": answer_text,
            "claims": [
                {
                    "text": answer_text,
                    "source_ids": [doc.get("id", "DB_META")]
                }
            ],
            "abstain": False,
        }
        evidence = [{
            "evidence_id": doc.get("id", "DB_META"),
            "locator": doc.get("document_number", doc.get("id", "DB_META")),
            "heading": doc.get("title", ""),
            "text": f"{doc.get('document_number')} do {authority} ban hành, hiệu lực từ {eff_from} đến {eff_to}. Trạng thái: {status_vi}.",
            "source_priority": 2,
            "metadata": doc,
        }]
    else:
        generation = {
            "answer": f"Không tìm thấy thông tin văn bản phù hợp trong cơ sở dữ liệu cho truy vấn: '{query}'.",
            "claims": [],
            "abstain": True,
        }
        evidence = []

    return {
        "generation": generation,
        "evidence": evidence,
        "citation_report": {"ok": True, "errors": [], "citation_accuracy": 1.0, "citation_coverage": 1.0},
    }


def hybrid_retrieve(state: AgentState) -> Dict[str, Any]:
    """Execute Hybrid Retrieval: Dense + BM25 + Reciprocal Rank Fusion."""
    query = state.get("query", "")
    dense_hits = dense_retrieve(query, top_k=20)
    bm25_hits = bm25_retrieve(query, top_k=20)

    # RRF Fusion
    fused_candidates = rrf_merge([dense_hits, bm25_hits], k=60, top_k=20)

    return {
        "dense_candidates": dense_hits,
        "bm25_candidates": bm25_hits,
        "candidates": fused_candidates,
    }


def evaluate_retrieval(state: AgentState) -> Dict[str, Any]:
    """Retrieval Evaluator: Rerank candidates and decide 3-branch CRAG action."""
    query = state.get("query", "")
    candidates = state.get("candidates", [])

    reranked = rerank(query, candidates, top_k=5)
    scores = [float(d.get("score", 0.0)) for d in reranked]

    action = decide_crag_action(scores, t_low=T_LOW, t_high=T_HIGH)

    return {
        "candidates": reranked,
        "relevance_scores": scores,
        "crag_action": action,
    }


def refine_internal_node(state: AgentState) -> Dict[str, Any]:
    """Knowledge Refinement: decompose into legal strips and filter by relevance threshold."""
    query = state.get("query", "")
    candidates = state.get("candidates", [])

    strips = refine_internal(query, candidates)
    updates: Dict[str, Any] = {"internal_evidence": strips}

    # In CORRECT branch, internal evidence is our final evidence
    if state.get("crag_action") == "CORRECT":
        updates["evidence"] = strips

    return updates


def rewrite_query_node(state: AgentState) -> Dict[str, Any]:
    """Query Rewrite: transform query via dynamic QueryRewriter."""
    query = state.get("query", "")
    rewriter = get_query_rewriter()
    rewritten = rewriter.rewrite(query)
    return {
        "rewritten_query": rewritten.search_query,
        "trace_meta": {
            "legal_entities": rewritten.legal_entities,
        }
    }


def web_search_node(state: AgentState) -> Dict[str, Any]:
    """Controlled Web Search: fetch external documents via ToolRegistry."""
    rewritten_query = state.get("rewritten_query") or state.get("query", "")
    tool_res = get_tool_registry().execute("controlled_web_search", query=rewritten_query, max_results=4)
    external_strips = tool_res.data if tool_res.success and tool_res.data else []
    return {"external_evidence": external_strips}


def select_external_node(state: AgentState) -> Dict[str, Any]:
    """Filter and refine external crawled web evidence."""
    query = state.get("query", "")
    external_evidence = state.get("external_evidence", [])

    refined_external = refine_external(query, external_evidence)
    updates: Dict[str, Any] = {"external_evidence": refined_external}

    if state.get("crag_action") == "INCORRECT":
        updates["evidence"] = refined_external

    return updates


def merge_evidence_node(state: AgentState) -> Dict[str, Any]:
    """Merge internal and external evidence with priority ranking (Ambiguous branch)."""
    internal = state.get("internal_evidence", [])
    external = state.get("external_evidence", [])

    merged = merge_evidence(internal, external, max_items=8)
    return {"evidence": merged}


def generate_answer(state: AgentState) -> Dict[str, Any]:
    """Generate structured response strictly constrained to evidence with citations."""
    query = state.get("query", "")
    evidence = state.get("evidence", [])
    memory_context = state.get("memory_context", "")

    # Format Evidence context
    context_lines = []
    evidence_map = {}
    for ev in evidence:
        sid = ev.get("strip_id") or ev.get("locator") or ev.get("evidence_id")
        heading = ev.get("heading", "")
        text = ev.get("text", "")
        context_lines.append(f"[{sid}] {heading}\n{text}")
        evidence_map[sid] = ev

    context_str = "\n\n".join(context_lines) if context_lines else "KHÔNG CÓ EVIDENCE NÀO."

    # If evidence is completely empty or all below relevance
    if not evidence or len(evidence) == 0:
        abstain_resp = {
            "answer": "Chưa đủ căn cứ pháp lý để kết luận.",
            "claims": [],
            "abstain": True,
        }
        return {"generation": abstain_resp}

    # Build Prompt adhering to Listing 3.14 and 5.2
    prompt = f"""BẠN LÀ TRỢ LÝ HỖ TRỢ TRA CỨU TUÂN THỦ PHÁP LÝ DOANH NGHIỆP.
Chỉ trả lời dựa duy nhất trên EVIDENCE PHÁP LÝ HIỆN TẠI được cung cấp dưới đây.

YÊU CẦU BẮT BUỘC:
1. Tuyệt đối không tự suy đoán hoặc sáng tạo quy định pháp luật.
2. Mọi kết luận pháp lý phải được gắn kèm [source_id] của evidence tương ứng.
3. Không tự tạo số hiệu văn bản, tên Điều/Khoản ngoài danh mục evidence.
4. Nếu evidence có mâu thuẫn, chỉ rõ sự khác biệt và ưu tiên văn bản có hiệu lực.
5. Nếu chưa đủ căn cứ, trả lời rõ ràng: "Chưa đủ căn cứ pháp lý để kết luận."
6. Định dạng đầu ra: Bắt buộc trả về đúng JSON Schema quy định:
   {{
     "answer": "Nội dung trả lời súc tích đầy đủ căn cứ...",
     "claims": [
       {{"text": "Mệnh đề kết luận 1", "source_ids": ["E1"]}},
       {{"text": "Mệnh đề kết luận 2", "source_ids": ["E2"]}}
     ],
     "abstain": false
   }}

BOI CANH CLIENT (Chi dung de hieu hoan canh, khong co gia tri phap ly):
{memory_context if memory_context else "Khong co"}

EVIDENCE PHAP LY HIEN TAI:
{context_str}

CÂU HỎI:
{query}
"""

    llm = get_chat_model()
    generation: Dict[str, Any] = {}

    if llm is not None:
        try:
            res = llm.invoke(prompt)
            raw_text = res.content if hasattr(res, "content") else str(res)
            # Extract JSON block
            json_m = re.search(r"\{[\s\S]*\}", raw_text)
            if json_m:
                generation = json.loads(json_m.group(0))
            else:
                generation = {"answer": raw_text, "claims": [], "abstain": False}
        except Exception as e:
            # Fallback deterministic answer synthesis from top evidence
            top_ev = evidence[0]
            sid = top_ev.get("strip_id") or top_ev.get("locator")
            ans = f"Theo quy định tại {top_ev.get('heading')}: {top_ev.get('text')[:300]} [{sid}]."
            generation = {
                "answer": ans,
                "claims": [{"text": ans, "source_ids": [sid]}],
                "abstain": False,
            }
    else:
        # Deterministic offline synthesis
        top_ev = evidence[0]
        sid = top_ev.get("strip_id") or top_ev.get("locator")
        ans = f"Căn cứ vào quy định tại {top_ev.get('heading')}: {top_ev.get('text')[:300]} [{sid}]."
        generation = {
            "answer": ans,
            "claims": [{"text": ans, "source_ids": [sid]}],
            "abstain": False,
        }

    return {"generation": generation}


def validate_citations_node(state: AgentState) -> Dict[str, Any]:
    """Validate citations against active evidence and temporal validity (Listing 3.13)."""
    generation = state.get("generation", {})
    evidence = state.get("evidence", [])
    as_of_date = state.get("as_of_date")

    # Build evidence map
    # Build comprehensive evidence map indexing all known locators/identifiers
    evidence_map = {}
    for ev in evidence:
        for k in ["strip_id", "locator", "evidence_id", "document_id", "document_number"]:
            val = ev.get(k)
            if val:
                evidence_map[str(val)] = ev
        # Also check nested metadata
        meta = ev.get("metadata", {})
        for k in ["strip_id", "locator", "evidence_id", "document_id", "document_number", "id"]:
            val = meta.get(k)
            if val:
                evidence_map[str(val)] = ev
    report = validate_citations(generation, evidence_map, as_of_date=as_of_date)
    return {"citation_report": report}

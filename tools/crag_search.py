"""Internal legal knowledge retrieval tool for the CRAG agent."""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from config import DB_PATH, T_HIGH, T_LOW, TOP_K_BM25, TOP_K_DENSE
from logging_config import get_logger, timed_stage
from retrieval.bm25 import bm25_retrieve
from retrieval.dense import dense_retrieve
from retrieval.fusion import rrf_merge
from retrieval.refine import refine_internal
from retrieval.reranker import decide_crag_action, rerank
from tools.base import BaseLegalTool

log = get_logger(__name__)

_ACTION_GUIDANCE = {
    "CORRECT": (
        "Bằng chứng nội bộ đầy đủ và liên quan cao. Có thể trả lời trực tiếp dựa trên các "
        "evidence này, không cần tra cứu thêm."
    ),
    "AMBIGUOUS": (
        "Bằng chứng nội bộ chỉ liên quan MỘT PHẦN. Cân nhắc gọi thêm controlled_web_search "
        "(với một câu truy vấn tìm kiếm cụ thể, súc tích) trên các cổng thông tin pháp luật "
        "chính thống để bổ sung bằng chứng trước khi trả lời."
    ),
    "INCORRECT": (
        "Bằng chứng nội bộ KHÔNG đủ liên quan (có thể kho tri thức nội bộ không có văn bản "
        "này). Bạn NÊN gọi controlled_web_search trước khi trả lời. Nếu tìm kiếm ngoài cũng "
        "không ra bằng chứng phù hợp, hãy trả lời 'Chưa đủ căn cứ pháp lý để kết luận.' thay "
        "vì suy đoán."
    ),
}


class CragSearchInput(BaseModel):
    """Input argument schema for the CRAG internal-knowledge tool."""
    query: str = Field(..., description="Câu hỏi hoặc chủ đề pháp lý cần tra cứu trong kho tri thức nội bộ")


CATALOG_KEYWORDS = [
    "nhóm văn bản", "văn bản đã nạp", "danh mục", "danh sách", "tổng quan",
    "uploads", "có những văn bản", "kho tri thức có", "kho dữ liệu có",
    "tài liệu đã nạp", "những luật nào", "văn bản hiện có", "văn bản nào"
]

def _is_catalog_query(query: str) -> bool:
    q_lower = query.lower()
    return any(k in q_lower for k in CATALOG_KEYWORDS)

def _get_catalog_evidence(db_path: str = str(DB_PATH)) -> List[Dict[str, Any]]:
    if not os.path.exists(db_path):
        return []
    try:
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            rows = cur.execute(
                "SELECT id, document_number, title, document_type, issuing_authority, effective_from FROM documents"
            ).fetchall()
            if not rows:
                return []

            catalog_items = []
            for r in rows:
                doc_id, doc_num, title, doc_type, auth, eff_from = r
                chunks = cur.execute(
                    "SELECT DISTINCT heading FROM document_chunks WHERE document_id = ? AND heading IS NOT NULL AND heading != '' LIMIT 15",
                    (doc_id,)
                ).fetchall()
                headings = [c[0] for c in chunks if c[0]]
                heading_summary = f"Các phần/điều khoản chính đã được nạp: {', '.join(headings)}." if headings else ""

                catalog_items.append({
                    "strip_id": f"CATALOG_{doc_id}",
                    "document_id": doc_id,
                    "document_number": doc_num,
                    "document_title": title,
                    "heading": f"Tổng quan: {title} (Số hiệu: {doc_num})",
                    "text": (
                        f"Văn bản: {title} (Số hiệu: {doc_num}, cơ quan ban hành: {auth or 'Quốc hội'}, "
                        f"hiệu lực: {eff_from or 'Đã có hiệu lực'}). {heading_summary}"
                    ),
                    "score": 0.98,
                    "source_priority": 1,
                    "retrieval_source": "internal",
                })
            return catalog_items
    except Exception as e:
        log.warning("[CRAG] Failed to query catalog: %s", e)
        return []


_ARTICLE_QUERY_RE = re.compile(r"[Đđ]i[ềe]u\s*(\d+)\b")


def _extract_article_number(query: str) -> str | None:
    """Extract explicit article number from query if present (e.g. 'Điều 25' -> '25')."""
    match = _ARTICLE_QUERY_RE.search(query)
    return match.group(1) if match else None


def _get_article_evidence(article_number: str, db_path: str = str(DB_PATH)) -> List[Dict[str, Any]]:
    """Fetch all clauses of a specified article directly from document chunks."""
    if not os.path.exists(db_path):
        return []
    try:
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            rows = cur.execute(
                """
                SELECT dc.id, dc.heading, dc.content, dc.clause, d.document_number
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.article = ? AND d.status = 'READY'
                ORDER BY dc.chunk_index
                """,
                (f"Điều {article_number}",),
            ).fetchall()
            return [
                {
                    "strip_id": r[0],
                    "heading": r[1] or f"Điều {article_number}",
                    "text": r[2],
                    "score": 0.99,
                    "source_priority": 1,
                    "retrieval_source": "internal_exact_locator",
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("[CRAG] Failed to query exact Điều locator: %s", e)
        return []


def crag_search(query: str, db_path: str = str(DB_PATH)) -> Dict[str, Any]:
    """Hybrid retrieval + self-correction over the indexed legal knowledge base."""
    if _is_catalog_query(query):
        catalog = _get_catalog_evidence(db_path)
        if catalog:
            with timed_stage(log, "RETRIEVE:DENSE", query=query[:60]):
                dense_hits = dense_retrieve(query, top_k=TOP_K_DENSE)
            with timed_stage(log, "RETRIEVE:BM25", query=query[:60]):
                bm25_hits = bm25_retrieve(query, top_k=TOP_K_BM25)
            with timed_stage(log, "RETRIEVE:RRF", query=query[:60]):
                fused = rrf_merge([dense_hits, bm25_hits], top_k=10)
            with timed_stage(log, "RETRIEVE:RERANK", query=query[:60]):
                reranked = rerank(query, fused, top_k=3)
            with timed_stage(log, "RETRIEVE:REFINE", query=query[:60]):
                refined = refine_internal(query, reranked)
            strips = catalog + refined
            return {
                "crag_action": "CORRECT",
                "guidance": _ACTION_GUIDANCE["CORRECT"],
                "evidence": strips[:6],
                "dense_candidates": len(dense_hits),
                "bm25_candidates": len(bm25_hits),
            }

    with timed_stage(log, "RETRIEVE:DENSE", query=query[:60]):
        dense_hits = dense_retrieve(query, top_k=TOP_K_DENSE)
    with timed_stage(log, "RETRIEVE:BM25", query=query[:60]):
        bm25_hits = bm25_retrieve(query, top_k=TOP_K_BM25)
    with timed_stage(log, "RETRIEVE:RRF", query=query[:60]):
        fused = rrf_merge([dense_hits, bm25_hits], top_k=20)
    with timed_stage(log, "RETRIEVE:RERANK", query=query[:60]):
        reranked = rerank(query, fused, top_k=5)
    scores = [float(d.get("score", 0.0)) for d in reranked]
    action = decide_crag_action(scores, t_low=T_LOW, t_high=T_HIGH)
    with timed_stage(log, "RETRIEVE:REFINE", query=query[:60]):
        strips = refine_internal(query, reranked)

    # Exact locator fast-path for explicitly referenced articles.
    article_number = _extract_article_number(query)
    if article_number:
        article_strips = _get_article_evidence(article_number, db_path)
        if article_strips:
            existing_ids = {s.get("strip_id") for s in strips}
            strips = article_strips + [s for s in strips if s.get("strip_id") not in existing_ids]
            action = "CORRECT"

    result = {
        "crag_action": action,
        "guidance": _ACTION_GUIDANCE[action],
        "evidence": strips,
        "dense_candidates": len(dense_hits),
        "bm25_candidates": len(bm25_hits),
    }
    return result


class CragSearchTool(BaseLegalTool):
    """Internal legal knowledge retrieval tool with hybrid search, fusion, and reranking."""

    name: str = "crag_search"
    description: str = (
        "Tra cứu kho tri thức pháp lý NỘI BỘ đã được nạp và lập chỉ mục (văn bản, Điều/Khoản). "
        "Luôn gọi tool này TRƯỚC TIÊN cho mọi câu hỏi về quy định, quyền, nghĩa vụ, điều kiện "
        "pháp lý. Trả về danh sách evidence (có source_id) kèm đánh giá độ tin cậy để bạn quyết "
        "định có cần gọi controlled_web_search bổ sung hay không trước khi trả lời."
    )
    args_schema = CragSearchInput

    def execute(self, query: str) -> Dict[str, Any]:
        return crag_search(query)

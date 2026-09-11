"""Schema-Driven Dynamic Query Rewriting and Expansion.

Replaces hardcoded stop-phrase lists with structured semantic reformulation,
modeled after Hermes Agent web query expansion and OpenClaw tool query contracts.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import OFFICIAL_DOMAINS
from llm import get_chat_model
from tools.database import extract_document_numbers


class RewrittenQuery(BaseModel):
    """Schema representing an optimized search query for official legal portals."""
    original_query: str
    search_query: str = Field(..., description="Optimized search query formatted for web retrieval")
    legal_entities: List[str] = Field(default_factory=list, description="Extracted legal terms and provisions")
    domain_filter: List[str] = Field(default_factory=list)


class QueryRewriter:
    """Reformulates natural language inquiries into high-precision legal web queries."""

    def __init__(self, allowed_domains: Optional[List[str]] = None):
        self.allowed_domains = allowed_domains or list(OFFICIAL_DOMAINS)[:3]

    def rewrite(self, query: str) -> RewrittenQuery:
        """Dynamically reformulate user query for official portal searching."""
        q_clean = query.strip()
        doc_nums = extract_document_numbers(q_clean)

        # 1. Try LLM structured query rewrite if model is available
        llm = get_chat_model()
        if llm is not None:
            llm_result = self._rewrite_with_llm(llm, q_clean, doc_nums)
            if llm_result is not None:
                return llm_result

        # 2. Rule-based linguistic reformulation (no hardcoded conversational stop-word lists)
        return self._rewrite_linguistically(q_clean, doc_nums)

    def _rewrite_with_llm(self, llm: Any, query: str, doc_nums: List[str]) -> Optional[RewrittenQuery]:
        """Use LLM to expand synonyms and optimize search string."""
        prompt = f"""Bạn là bộ tối ưu hóa truy vấn tìm kiếm văn bản pháp luật (Legal Query Rewriter).
Hãy chuyển đổi câu hỏi thông thường của người dùng thành từ khóa tìm kiếm chính xác trên cổng thông tin điện tử nhà nước (vbpl.vn, chinhphu.vn):
- Giữ nguyên số hiệu văn bản (nếu có): {doc_nums}
- Bỏ các từ ngữ giao tiếp thừa
- Giữ lại các thuật ngữ pháp lý cốt lõi (ví dụ: điều kiện, thủ tục, hồ sơ, thời hạn)

Định dạng JSON đầu ra:
{{
  "search_query": "từ khóa tìm kiếm súc tích",
  "legal_entities": ["thực thể 1", "thực thể 2"]
}}

CÂU HỎI: "{query}"
"""
        try:
            res = llm.invoke(prompt)
            raw = res.content if hasattr(res, "content") else str(res)
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                data = json.loads(m.group(0))
                return RewrittenQuery(
                    original_query=query,
                    search_query=data.get("search_query", query),
                    legal_entities=data.get("legal_entities", doc_nums),
                    domain_filter=self.allowed_domains,
                )
        except Exception:
            pass

        return None

    def _rewrite_linguistically(self, query: str, doc_nums: List[str]) -> RewrittenQuery:
        """Linguistic normalization extracting content words and legal patterns."""
        # Extract legal document references or core noun phrases
        words = query.split()
        # Keep words longer than 1 character, strip punctuation
        content_words = [re.sub(r"[^\w/]", "", w) for w in words if len(w) > 1]
        cleaned_str = " ".join([w for w in content_words if w])

        # If document number exists, emphasize it
        if doc_nums:
            search_str = f"{' '.join(doc_nums)} {cleaned_str}".strip()
        else:
            search_str = cleaned_str

        return RewrittenQuery(
            original_query=query,
            search_query=search_str,
            legal_entities=doc_nums,
            domain_filter=self.allowed_domains,
        )


_GLOBAL_REWRITER: Optional[QueryRewriter] = None


def get_query_rewriter() -> QueryRewriter:
    global _GLOBAL_REWRITER
    if _GLOBAL_REWRITER is None:
        _GLOBAL_REWRITER = QueryRewriter()
    return _GLOBAL_REWRITER

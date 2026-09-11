"""Dynamic Semantic Intent Classifier and Query Router.

Replaces hardcoded string checks with schema-driven classification
inspired by OpenClaw tool routing and Hermes Agent intent detection.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from llm import get_chat_model
from tools.database import extract_document_numbers


class RouteIntent(BaseModel):
    """Schema for query routing decision."""
    route: Literal["database", "rag", "general"] = Field(
        ...,
        description="Target routing path: 'database' (metadata/dates/status), 'rag' (legal content/rights/duties), or 'general' (greeting/help)"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Explanation for routing decision")
    detected_document_numbers: List[str] = Field(default_factory=list)
    primary_legal_topics: List[str] = Field(default_factory=list)


class RouterPolicy:
    """Configurable routing rules and heuristics for offline fallback."""

    # General conversational greetings
    GREETING_PATTERNS: List[str] = [
        r"^(xin\s+chào|chào\s+bạn|hello|hi\b|alo\b|hướng\s+dẫn\s+sử\s+dụng|bạn\s+là\s+ai)",
    ]

    # Patterns indicating metadata / validity / promulgation inquiries
    METADATA_PATTERNS: List[str] = [
        r"(còn\s+hiệu\s+lực|hết\s+hiệu\s+lực|ngày\s+có\s+hiệu\s+lực|ngày\s+ban\s+hành)",
        r"(thay\s+thế\s+bởi|hướng\s+dẫn\s+thi\s+hành|văn\s+bản\s+hướng\s+dẫn)",
        r"(số\s+hiệu\s+chính\s+xác|do\s+cơ\s+quan\s+nào\s+ban\s+hành)",
        r"(áp\s+dụng\s+từ\s+thời\s+điểm\s+nào|đã\s+phát\s+sinh\s+hiệu\s+lực\s+chưa)",
    ]


class SemanticRouter:
    """Classifies user intent into optimal execution pathways."""

    def __init__(self, policy: Optional[RouterPolicy] = None):
        self.policy = policy or RouterPolicy()

    def route(self, query: str) -> RouteIntent:
        """Classify query intent dynamically using LLM or structured heuristics."""
        q_clean = query.strip()
        doc_numbers = extract_document_numbers(q_clean)

        # 1. Try LLM structured classification if model is available
        llm = get_chat_model()
        if llm is not None:
            intent = self._classify_with_llm(llm, q_clean, doc_numbers)
            if intent is not None:
                return intent

        # 2. Rule-based heuristic classification
        return self._classify_heuristically(q_clean, doc_numbers)

    def _classify_with_llm(self, llm: Any, query: str, doc_numbers: List[str]) -> Optional[RouteIntent]:
        """Classify query intent using LLM structured output."""
        prompt = f"""Bạn là bộ phân loại ý định (Intent Classifier) cho Trợ lý Pháp lý.
Phân loại câu hỏi của người dùng vào 1 trong 3 route:
- "database": Tra cứu số hiệu, ngày ban hành, ngày có hiệu lực, trạng thái còn/hết hiệu lực, hoặc quan hệ thay thế/hướng dẫn giữa các văn bản.
- "rag": Tra cứu quy định nội dung, điều kiện, hồ sơ, trình tự, thủ tục, quyền và nghĩa vụ theo pháp luật.
- "general": Lời chào, hỏi thăm thông thường, hướng dẫn sử dụng.

Định dạng đầu ra: Bắt buộc trả về đúng JSON:
{{
  "route": "database" | "rag" | "general",
  "reasoning": "Lý do ngắn gọn...",
  "detected_document_numbers": {json.dumps(doc_numbers)},
  "primary_legal_topics": ["Chủ đề 1", "Chủ đề 2"]
}}

CÂU HỎI: "{query}"
"""
        try:
            res = llm.invoke(prompt)
            raw = res.content if hasattr(res, "content") else str(res)
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                data = json.loads(m.group(0))
                return RouteIntent(**data)
        except Exception:
            pass

        return None

    def _classify_heuristically(self, query: str, doc_numbers: List[str]) -> RouteIntent:
        """Rule-based heuristic classification using configured regex patterns."""
        q_lower = query.lower()

        # Check greeting
        for pat in self.policy.GREETING_PATTERNS:
            if re.search(pat, q_lower, re.IGNORECASE) and len(query.split()) <= 5:
                return RouteIntent(
                    route="general",
                    reasoning="Phát hiện lời chào thông thường",
                    detected_document_numbers=doc_numbers,
                )

        # Check metadata query
        for pat in self.policy.METADATA_PATTERNS:
            if re.search(pat, q_lower, re.IGNORECASE):
                return RouteIntent(
                    route="database",
                    reasoning="Truy vấn ngày hiệu lực, ban hành hoặc trạng thái văn bản",
                    detected_document_numbers=doc_numbers,
                )

        # If question contains document number and is very short (< 10 words), likely metadata lookup
        if doc_numbers and len(query.split()) <= 10:
            return RouteIntent(
                route="database",
                reasoning="Truy vấn trực tiếp số hiệu văn bản pháp lý",
                detected_document_numbers=doc_numbers,
            )

        # Default to full CRAG RAG
        return RouteIntent(
            route="rag",
            reasoning="Tra cứu quy định pháp luật chi tiết",
            detected_document_numbers=doc_numbers,
        )


_GLOBAL_ROUTER: Optional[SemanticRouter] = None


def get_semantic_router() -> SemanticRouter:
    global _GLOBAL_ROUTER
    if _GLOBAL_ROUTER is None:
        _GLOBAL_ROUTER = SemanticRouter()
    return _GLOBAL_ROUTER

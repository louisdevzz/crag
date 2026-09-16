"""Follow-up Question Generation: a small, isolated LLM call that reads the
answer just produced and suggests what the user would plausibly ask next.

Deliberately NOT part of the main answer generation prompt: the main answer
must stay unconstrained natural prose (see `agent/prompts.py`), so forcing it
to also emit a structured `follow_up_questions` field would reintroduce the
JSON-formatting pressure that fight against natural tone. This mirrors how
ChatGPT/Perplexity implement "related questions" — a separate, cheap
completion grounded on the actual exchange, not a hardcoded template keyed on
keywords in the question (the previous frontend implementation, which the
user correctly flagged as fake).
"""
from __future__ import annotations

import json
import re
from typing import List

from llm import get_chat_model_with_fallback as get_chat_model
from logging_config import get_logger

log = get_logger(__name__)

MAX_FOLLOW_UPS = 2
_ANSWER_CHARS_FOR_PROMPT = 1500

_PROMPT_TEMPLATE = """Đây là một lượt hỏi-đáp pháp lý vừa diễn ra:

Câu hỏi: {query}

Câu trả lời: {answer}

Đề xuất tối đa {max_items} câu hỏi tiếp theo NGẮN GỌN, TỰ NHIÊN mà người dùng có khả năng sẽ hỏi tiếp, dựa TRỰC TIẾP vào nội dung cụ thể đã nêu trong câu trả lời trên (ví dụ: một thủ tục, một mức thời hạn, một chủ thể được nhắc tới) — không phải câu hỏi chung chung có thể áp dụng cho bất kỳ chủ đề nào. Nếu câu trả lời không còn gì đáng hỏi tiếp, trả về mảng rỗng.

Chỉ trả về một mảng JSON các chuỗi, không kèm giải thích nào khác. Ví dụ định dạng: ["...", "..."]"""


def _extract_json_array(text: str) -> List[str]:
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def generate_follow_ups(query: str, answer: str) -> List[str]:
    """Return up to `MAX_FOLLOW_UPS` follow-up questions grounded in `answer`,
    or `[]` on any failure (no LLM available, malformed output, chit-chat
    turns with nothing to follow up on) — this is a UX nicety, never allowed
    to fail the turn."""
    if not answer or not answer.strip():
        return []

    llm = get_chat_model(temperature=0.3)
    if llm is None:
        return []

    prompt = _PROMPT_TEMPLATE.format(
        query=query.strip(),
        answer=answer.strip()[:_ANSWER_CHARS_FOR_PROMPT],
        max_items=MAX_FOLLOW_UPS,
    )
    try:
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content or "")
    except Exception as e:
        log.warning("[FOLLOW_UPS] generation failed (%s) -> no suggestions", e)
        return []

    return _extract_json_array(content)[:MAX_FOLLOW_UPS]

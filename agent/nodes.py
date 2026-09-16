"""LangGraph Node Implementations for the Legal CRAG ReAct Agent.

Agent Core is a genuine ReAct tool-calling loop (mirrors Hermes Agent's core
loop: call LLM -> if tool_calls, dispatch via registry, feed results back,
loop -> else the response is the final answer) — there is no separate router
node or fixed retrieval pipeline node; `crag_search` and `controlled_web_search`
are the only two things the model can call, and it decides for itself.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer

from agent.followups import generate_follow_ups
from agent.prompts import build_system_prompt
from agent.state import AgentState
from legal.citations import validate_citations
from llm import get_chat_model_with_fallback as get_chat_model
from logging_config import get_logger
from tools.registry import get_tool_registry

log = get_logger(__name__)

# Iteration cap: at most this many agent->tools round trips before the agent
# node stops offering tools and is forced to answer with whatever evidence it
# already gathered (never loop forever on a model that keeps calling tools).
MAX_TOOL_ROUNDS = 3

# Independent bound on how many times the model gets nudged about an evidence gap
# before its answer is simply accepted as-is — separate from MAX_TOOL_ROUNDS because
# a nudge (plain SystemMessage, no tool_calls) never increments the tool-round count.
MAX_EVIDENCE_GAP_NUDGES = 2

_GENERAL_FALLBACK = {
    "answer": "Xin chào! Tôi là trợ lý AI hỗ trợ tra cứu tuân thủ pháp lý doanh nghiệp. Bạn cần tôi tra cứu quy định gì?",
    "claims": [],
    "abstain": False,
}


_FORMAT_RETRY_NOTICE = (
    "Định dạng câu trả lời trước đó KHÔNG đúng yêu cầu (không phải JSON hợp lệ). Hãy trả lời "
    "lại NGUYÊN VẸN nội dung đó nhưng đúng định dạng JSON bắt buộc: "
    '{"answer": "...", "claims": [...], "abstain": false} — CHỈ trả về JSON, không kèm văn bản '
    "nào khác."
)


_FINAL_ROUND_NOTICE = (
    "Bạn đã dùng hết số lượt gọi công cụ cho phép trong lượt hỏi này. Hãy đưa ra câu trả lời CUỐI CÙNG "
    "ngay bây giờ: nếu có bằng chứng (evidence) đã thu thập được ở các tool_call phía trên, hãy tổng hợp "
    "và trích dẫn mã nguồn [source_id] tương ứng; nếu hoàn toàn không có bằng chứng phù hợp, trả lời đúng "
    "nguyên văn 'Chưa đủ căn cứ pháp lý để kết luận.' TUYỆT ĐỐI không chào hỏi, không hỏi lại, không nói "
    "cần tra cứu thêm."
)


_EVIDENCE_GAP_NUDGE_PREFIX = "[Ghi chú nội bộ] "


def _evidence_gap_nudge(state: AgentState) -> Optional[str]:
    """Describe, in plain language, that the internal evidence still looks weak —
    never which tool to call next or with what argument. The model reads this
    exactly like any other tool result and decides for itself whether and how to
    search further; naming the fix here would turn tool selection into an if/else
    in the harness instead of a model decision. The signal itself
    (`crag_action`) comes from the cross-encoder reranker's calibrated score
    thresholds (`retrieval.reranker.decide_crag_action`), not from keyword
    matching — this function adds no domain-specific heuristics of its own."""
    tool_trace = state.get("tool_trace") or []
    crag_calls = [t for t in tool_trace if t.get("tool") == "crag_search"]
    if not crag_calls:
        return None

    web_search_tried = any(t.get("tool") == "controlled_web_search" for t in tool_trace)
    last_crag_action = crag_calls[-1].get("crag_action")
    if not web_search_tried and last_crag_action != "CORRECT":
        return (
            f"{_EVIDENCE_GAP_NUDGE_PREFIX}Bằng chứng nội bộ hiện được đánh giá là {last_crag_action}, "
            "chưa đủ tin cậy để trả lời trực tiếp. Hãy tự quyết định có cần tìm kiếm bổ sung hay không "
            "trước khi đưa câu trả lời cuối cùng."
        )
    return None


_LEAKED_FUNCTION_RE = re.compile(r"<function=([\w.\-]+)>([\s\S]*?)</function>", re.IGNORECASE)
_LEAKED_PARAM_RE = re.compile(r"<parameter=([\w.\-]+)>([\s\S]*?)</parameter>", re.IGNORECASE)


def _extract_leaked_tool_calls(content: Any) -> Optional[List[Dict[str, Any]]]:
    """Some tool-calling-tuned open models (Qwen/Hermes chat template) occasionally leak their
    tool-call intent as `<tool_call><function=name><parameter=k>v</parameter></function></tool_call>`
    text in `content` instead of populating the API's structured `tool_calls` field. Parse that
    format back into normal `AIMessage.tool_calls` shape so the rest of the loop is unaffected —
    Hermes Agent's own bridge (`acp_openai_bridge.py::extract_tool_calls_from_text`) handles the
    same class of provider quirk the same way."""
    text = content if isinstance(content, str) else str(content or "")
    if "<function=" not in text:
        return None
    calls: List[Dict[str, Any]] = []
    for name, body in _LEAKED_FUNCTION_RE.findall(text):
        args = {k: v.strip() for k, v in _LEAKED_PARAM_RE.findall(body)}
        calls.append({"name": name, "args": args, "id": f"leaked_{uuid.uuid4().hex[:8]}", "type": "tool_call"})
    return calls or None


def _normalize_claims(claims: Any) -> List[Dict[str, Any]]:
    """Defensively coerce whatever shape the model produced for `claims` into the
    `{"text": str, "source_ids": [str]}` contract `legal.citations.validate_citations` expects —
    a model occasionally emits a bare list of strings instead of claim objects."""
    if not isinstance(claims, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for c in claims:
        if isinstance(c, dict):
            normalized.append({"text": c.get("text", ""), "source_ids": c.get("source_ids", []) or []})
        elif isinstance(c, str):
            normalized.append({"text": c, "source_ids": []})
    return normalized


def _parse_generation_flexible(content: Any, evidence: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flexible parse: handles both JSON format and natural Markdown prose,
    extracting claims, citations, and abstain status seamlessly."""
    text = content if isinstance(content, str) else str(content or "")
    evidence = evidence or []

    # 1. First, attempt JSON parsing
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "answer" in parsed:
                return {
                    "answer": parsed.get("answer", ""),
                    "claims": _normalize_claims(parsed.get("claims", [])),
                    "abstain": parsed.get("abstain", False),
                }
        except (json.JSONDecodeError, ValueError):
            pass

    # 2. If not valid JSON, treat the text as the natural Markdown answer
    clean_text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text).strip()
    clean_text = re.sub(r"<function=[\w.\-]+>[\s\S]*?</function>", "", clean_text).strip()

    if not clean_text:
        clean_text = _GENERAL_FALLBACK["answer"]

    # Extract claims with citations from text: e.g. [DOC_...], [CATALOG_...], [E1]
    claims: List[Dict[str, Any]] = []
    citation_regex = re.compile(r"\[([A-Za-z0-9_\-]+)\]")
    sentences = re.split(r"(?<=[.!?\n])\s+", clean_text)
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        cites = citation_regex.findall(s)
        if cites:
            claims.append({"text": s, "source_ids": cites})

    lower_text = clean_text.lower()
    abstain = "chưa đủ căn cứ pháp lý" in lower_text or "không đủ căn cứ pháp lý" in lower_text

    return {
        "answer": clean_text,
        "claims": claims,
        "abstain": abstain,
    }


def _deterministic_answer_from_evidence(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Offline/error fallback: synthesize a minimal grounded answer from the best evidence found so far."""
    if not evidence:
        return {"answer": "Chưa đủ căn cứ pháp lý để kết luận.", "claims": [], "abstain": True}
    top = evidence[0]
    sid = top.get("strip_id") or top.get("locator") or top.get("evidence_id")
    text = (top.get("text") or "")[:300]
    ans = f"Theo quy định tại {top.get('heading', '')}: {text} [{sid}]."
    return {"answer": ans, "claims": [{"text": ans, "source_ids": [sid]}], "abstain": False}


def agent_node(state: AgentState) -> Dict[str, Any]:
    """Agent Core: one LLM turn. Either emits tool_calls or produces the final answer."""
    messages = list(state.get("messages") or [])
    if not messages:
        messages = [
            SystemMessage(content=build_system_prompt(state)),
            HumanMessage(content=state.get("query", "")),
        ]

    llm = get_chat_model()
    if llm is None:
        log.warning("[AGENT] no LLM client -> deterministic fallback")
        fallback = _deterministic_answer_from_evidence(state.get("evidence", []))
        return {
            "messages": [AIMessage(content=json.dumps(fallback, ensure_ascii=False))],
            "generation": fallback,
        }

    tool_call_rounds = sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)
    allow_tools = tool_call_rounds < MAX_TOOL_ROUNDS
    tools_schema = get_tool_registry().to_openai_tools() if allow_tools else []

    # Round cap reached: tools are no longer offered, so nudge the model to actually
    # synthesize from whatever evidence it already gathered instead of free-generating
    # an unrelated greeting/non-answer (observed behavior without this reminder).
    final_round_reminder: Optional[SystemMessage] = None
    if not allow_tools:
        final_round_reminder = SystemMessage(content=_FINAL_ROUND_NOTICE)
        messages = messages + [final_round_reminder]

    bound = llm
    if tools_schema:
        try:
            bound = llm.bind_tools(tools_schema)
        except Exception as e:
            log.warning("[AGENT] bind_tools failed (%s) -> proceeding without tool-calling", e)

    try:
        ai_msg = bound.invoke(messages)
    except Exception as e:
        log.error("[AGENT] LLM call FAILED (%s) -> deterministic fallback from accumulated evidence", e)
        fallback = _deterministic_answer_from_evidence(state.get("evidence", []))
        return {
            "messages": [AIMessage(content=json.dumps(fallback, ensure_ascii=False))],
            "generation": fallback,
        }

    log.info(
        "[AGENT] round=%d tool_calls=%s content_chars=%d",
        tool_call_rounds, [tc["name"] for tc in (ai_msg.tool_calls or [])], len(ai_msg.content or ""),
    )

    if allow_tools and not ai_msg.tool_calls:
        leaked_calls = _extract_leaked_tool_calls(ai_msg.content)
        if leaked_calls is not None:
            log.warning("[AGENT] model leaked tool-call as text -> recovering %d call(s): %s", len(leaked_calls), [c["name"] for c in leaked_calls])
            ai_msg = AIMessage(content="", tool_calls=leaked_calls)
            return {"messages": [ai_msg]}

        # Corrective nudge, not corrective dictation: the harness is only allowed to
        # SURFACE a fact (evidence looks incomplete for what the user asked) as plain
        # text, the same shape as any other tool result the model reads — it never
        # fabricates a fake AIMessage naming which tool to call with which args on
        # the model's behalf. That would make crag_search/controlled_web_search
        # selection an if/else in the harness instead of a real agent decision (see
        # `.temp/hermes-agent/AGENTS.md`: "the core is a narrow waist; capability
        # lives at the edges" — domain judgment belongs to the model). Bounded like
        # every other retry loop in this file (MAX_EVIDENCE_GAP_NUDGES) so a model
        # that ignores the nudge still terminates instead of looping forever.
        nudge_count = sum(
            1 for m in messages
            if isinstance(m, SystemMessage) and m.content.startswith(_EVIDENCE_GAP_NUDGE_PREFIX)
        )
        if nudge_count < MAX_EVIDENCE_GAP_NUDGES:
            nudge = _evidence_gap_nudge(state)
            if nudge:
                log.info(
                    "[AGENT] evidence gap detected -> nudging model to decide its own next step (attempt %d/%d): %s",
                    nudge_count + 1, MAX_EVIDENCE_GAP_NUDGES, nudge[:160],
                )
                return {"messages": [SystemMessage(content=nudge)]}

    updates: Dict[str, Any] = {"messages": ([final_round_reminder] if final_round_reminder else []) + [ai_msg]}
    if not ai_msg.tool_calls:
        generation = _parse_generation_flexible(ai_msg.content, state.get("evidence", []))
        updates["generation"] = generation
        writer = get_stream_writer()
        writer({"final_answer": generation.get("answer", "")})
    return updates

def tool_node(state: AgentState) -> Dict[str, Any]:
    """Execute every tool call the agent just requested, via Tool Registry dispatch."""
    messages = state.get("messages") or []
    last = messages[-1]
    registry = get_tool_registry()
    writer = get_stream_writer()
    prior_trace = state.get("tool_trace") or []

    tool_messages: List[ToolMessage] = []
    new_evidence: List[Dict[str, Any]] = []
    new_trace: List[Dict[str, Any]] = []

    for call in last.tool_calls:
        name = call["name"]
        args = call.get("args", {}) or {}
        call_id = call["id"]

        # An identical (name, args) call already succeeded earlier this turn: skip
        # re-executing it (spares a network round trip, e.g. a slow web search) and
        # push the model to reuse the evidence it already has instead of stalling
        # out the MAX_TOOL_ROUNDS budget on repeats.
        if any(t.get("tool") == name and t.get("args") == args and t.get("success") for t in prior_trace):
            log.info("[TOOL] %s args=%s -> SKIPPED (duplicate of an already-executed call this turn)", name, args)
            tool_messages.append(ToolMessage(
                content=json.dumps({
                    "note": "Kết quả trùng lặp với lần gọi trước đó trong lượt này — hãy dùng bằng "
                            "chứng đã thu thập được ở trên để trả lời, không lặp lại truy vấn này nữa.",
                }, ensure_ascii=False),
                tool_call_id=call_id, name=name,
            ))
            continue

        writer({"tool_start": {"tool": name, "args": args}})

        result = registry.execute(name, **args)
        payload = result.data if (result.success and isinstance(result.data, dict)) else None
        evidence = list(payload.get("evidence", [])) if payload else []
        crag_action = payload.get("crag_action") if payload else None

        new_evidence.extend(evidence)
        new_trace.append({
            "tool": name, "args": args, "crag_action": crag_action,
            "success": result.success, "evidence_count": len(evidence),
            "aspects": payload.get("aspects") if payload else None,
        })

        if result.success:
            content = json.dumps({
                "crag_action": crag_action,
                "guidance": payload.get("guidance") if payload else None,
                "evidence": [
                    {
                        "source_id": e.get("strip_id") or e.get("locator") or e.get("evidence_id"),
                        "heading": e.get("heading", ""),
                        "text": e.get("text", ""),
                    }
                    for e in evidence
                ],
            }, ensure_ascii=False)
        else:
            content = json.dumps({"error": result.error}, ensure_ascii=False)

        tool_messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
        writer({"tool_end": {"tool": name, "success": result.success, "evidence_count": len(evidence)}})
        log.info("[TOOL] %s args=%s -> success=%s evidence=%d crag_action=%s", name, args, result.success, len(evidence), crag_action)

    return {"messages": tool_messages, "evidence": new_evidence, "tool_trace": new_trace}


def route_after_agent(state: AgentState) -> str:
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    if not state.get("generation"):
        # Final content failed strict JSON parsing and a reformat retry was just queued
        # (see agent_node) -> loop back to the agent for exactly one more attempt.
        return "agent"
    return "cite_validate"


def validate_citations_node(state: AgentState) -> Dict[str, Any]:
    """Validate citations against accumulated evidence and temporal validity."""
    generation = state.get("generation", {})
    evidence = state.get("evidence", [])
    as_of_date = state.get("as_of_date")

    evidence_map: Dict[str, Any] = {}
    for ev in evidence:
        for k in ["strip_id", "locator", "evidence_id", "document_id", "document_number"]:
            val = ev.get(k)
            if val:
                evidence_map[str(val)] = ev
        meta = ev.get("metadata", {})
        for k in ["strip_id", "locator", "evidence_id", "document_id", "document_number", "id"]:
            val = meta.get(k)
            if val:
                evidence_map[str(val)] = ev

    report = validate_citations(generation, evidence_map, as_of_date=as_of_date)
    log.info(
        "[CITE_VALIDATE] ok=%s accuracy=%.2f coverage=%.2f errors=%d",
        report.get("ok"), report.get("citation_accuracy", 0.0), report.get("citation_coverage", 0.0), len(report.get("errors", [])),
    )
    follow_ups = generate_follow_ups(state.get("query", ""), generation.get("answer", ""))
    return {"citation_report": report, "follow_up_questions": follow_ups}


def derive_route_and_action(tool_trace: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Post-hoc classification of a completed turn for logging/analytics/API compatibility
    (`route`/`crag_action` are no longer control-flow decisions, just an observability summary
    of which tool(s) the agent actually chose to call)."""
    crag_calls = [t for t in tool_trace if t.get("tool") == "crag_search" and t.get("success")]
    if crag_calls:
        return "rag", crag_calls[-1].get("crag_action") or "AMBIGUOUS"
    if tool_trace:
        return "rag", "AMBIGUOUS"
    return "general", "CORRECT"

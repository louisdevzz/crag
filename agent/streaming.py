"""SSE helpers for the ReAct Agent Core: node/stage progress mapping, and
progressive delivery of the (already-complete) final answer text.

`agent_node` (agent/nodes.py) calls the LLM non-streaming — tool-calling and
JSON-format-retry logic need the complete response to decide the next step,
and interleaving true token-level streaming with tool-call detection is not
reliably supported across providers (Groq/OpenAI/OpenRouter/Ollama disagree on
whether a tool-calling turn emits partial `content` before/instead of
`tool_calls`). Once the turn's final answer is known in full, it is split into
small pieces and delivered as a sequence of `token` SSE events instead — the
frontend still sees a typewriter effect, just not truly live mid-generation.
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional

# Maps LangGraph node names to a coarse 0-3 progress stage for the frontend's
# fixed 4-step `AgentProgress` UI (frontend/src/components/chat/agent-progress.tsx):
#   0 - first Agent Core turn (deciding which tool, if any, to call)
#   1 - Tool Registry executing whatever was requested (crag_search / controlled_web_search)
#   2 - Agent Core reasoning again over tool results (may call more tools, or answer)
#   3 - citation validation of the final answer
# The SSE loop (api/main.py) tracks how many times "agent" has fired so the
# same node name maps to stage 0 the first time and stage 2 afterward.
NODE_STAGE: Dict[str, int] = {
    "agent": 0,
    "tools": 1,
    "cite_validate": 3,
}

AGENT_REASK_STAGE = 2


def node_stage(node_name: str, agent_call_index: int) -> Optional[int]:
    """Resolve a node's progress stage; `agent_call_index` is how many times the
    "agent" node has already fired *before* this occurrence (0 on the first call)."""
    if node_name == "agent":
        return 0 if agent_call_index == 0 else AGENT_REASK_STAGE
    return NODE_STAGE.get(node_name)


def chunk_text_for_pseudo_stream(text: str, chunk_size: int = 24) -> Iterator[str]:
    """Split a complete answer string into small pieces for progressive SSE delivery."""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

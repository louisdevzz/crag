"""SSE streaming helpers for progress mapping and text chunking."""
from __future__ import annotations

from typing import Dict, Iterator, Optional

# Map LangGraph node names to coarse progress stages for frontend display.
NODE_STAGE: Dict[str, int] = {
    "agent": 0,
    "tools": 1,
    "cite_validate": 3,
}

AGENT_REASK_STAGE = 2


def node_stage(node_name: str, agent_call_index: int) -> Optional[int]:
    """Resolve progress stage index for a given node and invocation count."""
    if node_name == "agent":
        return 0 if agent_call_index == 0 else AGENT_REASK_STAGE
    return NODE_STAGE.get(node_name)


def chunk_text_for_pseudo_stream(text: str, chunk_size: int = 24) -> Iterator[str]:
    """Split a complete answer string into small pieces for progressive SSE delivery."""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

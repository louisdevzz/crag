"""AgentState Definition for the Legal CRAG ReAct Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Shared scratchpad for one turn of the ReAct loop (agent <-> tools).

    Not cross-turn persisted: `agent.context.build_context` rebuilds
    `conversation_history`/`memory_context` from SQLite at the start of every
    turn; `messages` here is only this turn's tool-calling trajectory.
    """

    # 1. Request & Context (assembled by agent.runtime / agent.context before the graph runs)
    client_id: str
    session_id: str
    query: str
    as_of_date: Optional[str]
    memory_context: str
    conversation_history: str

    # 2. ReAct trajectory
    messages: Annotated[List[BaseMessage], add_messages]
    evidence: Annotated[List[Dict[str, Any]], operator.add]        # accumulated across every tool call this turn
    tool_trace: Annotated[List[Dict[str, Any]], operator.add]      # {"tool", "args", "crag_action", "success"} per call

    # 3. Generation & Verification Output
    generation: Dict[str, Any]                # {"answer": str, "claims": [...], "abstain": bool}
    citation_report: Dict[str, Any]           # Validation result from CitationValidator
    trace_meta: Dict[str, Any]                # Observability metadata

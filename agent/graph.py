"""LangGraph ReAct Agent Core: agent <-> tools loop (Agentic CRAG Architecture).

No router node, no fixed retrieval pipeline node: `agent_node` calls the LLM
with the two registered tools (`crag_search`, `controlled_web_search`) bound;
`tool_node` dispatches whatever the model asked for via the Tool Registry and
feeds results back; the loop repeats until the model answers without calling
a tool (or the iteration cap forces it to). This mirrors Hermes Agent's core
loop (CONTRIBUTING.md): call LLM -> if tool_calls, dispatch + append results
-> loop back to LLM.

No checkpointer either: cross-turn continuity is the Context Manager's job
(agent/context.py, backed by the durable `messages`/`memories` SQLite tables).
Each `invoke()` is a self-contained turn; `agent.runtime` assembles its input.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes import agent_node, route_after_agent, tool_node, validate_citations_node
from agent.state import AgentState


def build_crag_graph():
    """Build and compile the Agentic CRAG ReAct loop."""
    g = StateGraph(AgentState)

    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_node("cite_validate", validate_citations_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "agent": "agent", "cite_validate": "cite_validate"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("cite_validate", END)

    return g.compile()


# Lazy singleton instance (the graph is stateless across turns, so one compiled
# instance is safely shared by every request).
_COMPILED_GRAPH = None


def get_crag_app():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_crag_graph()
    return _COMPILED_GRAPH


if __name__ == "__main__":
    from agent.runtime import invoke_crag

    res = invoke_crag("Văn bản số 41/2024/QH15 còn hiệu lực không?")
    print("Agentic CRAG ReAct loop successfully invoked!")
    print("Route:", res.get("route"))
    print("Answer:", res.get("generation", {}).get("answer"))

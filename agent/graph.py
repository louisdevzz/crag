"""LangGraph ReAct agent core loop for the Legal CRAG assistant."""
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


# Lazy singleton instance for compiled graph.
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

"""LangGraph StateGraph Definition with 3-Branch Corrective RAG Workflow."""
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from agent.nodes import (
    evaluate_retrieval,
    generate_answer,
    hybrid_retrieve,
    merge_evidence_node,
    query_db,
    refine_internal_node,
    rewrite_query_node,
    route_question,
    select_external_node,
    validate_citations_node,
    web_search_node,
)
from agent.state import AgentState


def build_crag_graph(checkpointer: Any = None):
    """Build and compile the complete 3-branch Corrective RAG LangGraph workflow.

    Implements the official LangGraph architecture (https://docs.langchain.com/oss/python/langgraph/overview):
    - StateGraph(AgentState): Central state schema
    - Nodes: Pure transformation functions
    - START / END: Formal graph boundaries
    - Conditional Edges: 3-branch CRAG routing
    - Checkpointer: Thread-level persistence across conversation turns
    """
    g = StateGraph(AgentState)

    # 1. Register Nodes
    g.add_node("router", route_question)
    g.add_node("db", query_db)
    g.add_node("retrieve", hybrid_retrieve)
    g.add_node("evaluate", evaluate_retrieval)
    g.add_node("refine", refine_internal_node)
    g.add_node("rewrite", rewrite_query_node)
    g.add_node("web", web_search_node)
    g.add_node("select_web", select_external_node)
    g.add_node("merge", merge_evidence_node)
    g.add_node("generate", generate_answer)
    g.add_node("cite_validate", validate_citations_node)

    # 2. Entry Point from START
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: s.get("route", "rag"),
        {
            "database": "db",
            "rag": "retrieve",
            "general": "generate",
        },
    )

    # Database query path
    g.add_edge("db", "cite_validate")

    # Retrieval to Evaluator
    g.add_edge("retrieve", "evaluate")

    # 4. Conditional Branching after Evaluator (Listing 3.15)
    # CORRECT -> refine, AMBIGUOUS -> refine, INCORRECT -> rewrite
    g.add_conditional_edges(
        "evaluate",
        lambda s: s.get("crag_action", "AMBIGUOUS"),
        {
            "CORRECT": "refine",
            "AMBIGUOUS": "refine",
            "INCORRECT": "rewrite",
        },
    )

    # 5. Routing after Refinement
    # CORRECT -> generate
    # AMBIGUOUS -> rewrite (fetch external evidence to augment)
    g.add_conditional_edges(
        "refine",
        lambda s: "generate" if s.get("crag_action") == "CORRECT" else "rewrite",
        {
            "generate": "generate",
            "rewrite": "rewrite",
        },
    )

    # 6. External Web Search Chain
    g.add_edge("rewrite", "web")
    g.add_edge("web", "select_web")

    # 7. Routing after Web Selection
    # AMBIGUOUS -> merge (combine internal + external)
    # INCORRECT -> generate (external only)
    g.add_conditional_edges(
        "select_web",
        lambda s: "merge" if s.get("crag_action") == "AMBIGUOUS" else "generate",
        {
            "merge": "merge",
            "generate": "generate",
        },
    )

    # 8. Generation & Validation Exit
    g.add_edge("merge", "generate")
    g.add_edge("generate", "cite_validate")
    g.add_edge("cite_validate", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return g.compile(checkpointer=checkpointer)


# Lazy singleton instance with checkpointer
_COMPILED_GRAPH = None


def get_crag_app(checkpointer: Any = None):
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None or checkpointer is not None:
        _COMPILED_GRAPH = build_crag_graph(checkpointer=checkpointer)
    return _COMPILED_GRAPH


def invoke_crag(
    query: str,
    client_id: Optional[str] = None,
    session_id: Optional[str] = None,
    as_of_date: Optional[str] = None,
    memory_context: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """Convenience invoker applying official LangGraph thread_id configurable convention."""
    import uuid
    app = app or get_crag_app()
    cid = client_id or "default_client"
    sid = session_id or f"thread_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": sid}}
    state_input = {
        "client_id": cid,
        "session_id": sid,
        "query": query,
        "as_of_date": as_of_date,
        "memory_context": memory_context or "",
    }
    return app.invoke(state_input, config=config)


if __name__ == "__main__":
    res = invoke_crag("Văn bản số 41/2024/QH15 còn hiệu lực không?")
    print("CRAG StateGraph successfully invoked!")
    print("Route:", res.get("route"))
    print("Answer:", res.get("generation", {}).get("answer"))

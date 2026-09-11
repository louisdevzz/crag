"""LangGraph StateGraph Definition with 3-Branch Corrective RAG Workflow."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

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


def build_crag_graph():
    """Build and compile the complete 3-branch Corrective RAG LangGraph workflow."""
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

    # 2. Entry Point
    g.set_entry_point("router")

    # 3. Router Conditional Branching
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

    return g.compile()


# Lazy instance
_COMPILED_GRAPH = None


def get_crag_app():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_crag_graph()
    return _COMPILED_GRAPH


if __name__ == "__main__":
    app = get_crag_app()
    print("CRAG StateGraph successfully compiled!")

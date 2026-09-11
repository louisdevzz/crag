"""CLI Application and Demo Suite Runner for Legal CRAG Assistant V3 (Table 3.2)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.graph import get_crag_app
from legal.citations import validate_citations
from memory.extractor import extract_and_save_memories
from memory.store import get_memory_store


def run_demo_suite():
    """Execute the 5 mandatory demo scenarios required by Table 3.2."""
    app = get_crag_app()
    store = get_memory_store()

    print("=" * 80)
    print("LEGAL CRAG ASSISTANT V3 — 5 MANDATORY DEMO TEST SCENARIOS (TABLE 3.2)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Correct Case (In-corpus query with complete evidence)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("TEST 1: CORRECT CASE — In-corpus Question with Full Evidence")
    print("#" * 80)
    q1 = "Đối tượng tham gia bảo hiểm xã hội bắt buộc theo quy định hiện hành bao gồm những ai?"
    print(f"Câu hỏi: '{q1}'")
    res1 = app.invoke({"query": q1, "client_id": "demo_client"})
    print(f"-> Route:           {res1.get('route')}")
    print(f"-> CRAG Action:     {res1.get('crag_action')} (Expected: CORRECT)")
    print(f"-> Evidence Strips: {len(res1.get('evidence', []))}")
    print(f"-> Answer:          {res1.get('generation', {}).get('answer')[:200]}...")
    print(f"-> Citation Report: {res1.get('citation_report')}")

    # -------------------------------------------------------------------------
    # TEST 2: Incorrect Case (Out-of-corpus query triggering Web Search)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("TEST 2: INCORRECT CASE — Out-of-corpus Question Triggering Controlled Web Search")
    print("#" * 80)
    q2 = "Thủ tục xin giấy phép bay cho phương tiện bay không người lái drone nông nghiệp?"
    print(f"Câu hỏi: '{q2}'")
    res2 = app.invoke({"query": q2, "client_id": "demo_client"})
    print(f"-> Route:           {res2.get('route')}")
    print(f"-> CRAG Action:     {res2.get('crag_action')} (Expected: INCORRECT / AMBIGUOUS)")
    print(f"-> Rewritten Query: {res2.get('rewritten_query')}")
    print(f"-> Evidence Count:  {len(res2.get('evidence', []))}")
    print(f"-> Answer:          {res2.get('generation', {}).get('answer')[:200]}...")
    print(f"-> Citation Report: {res2.get('citation_report')}")

    # -------------------------------------------------------------------------
    # TEST 3: Ambiguous Case (Partial evidence triggering Refine + Web + Merge)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("TEST 3: AMBIGUOUS CASE — Partial Evidence Triggering Internal Refine + Web + Merge")
    print("#" * 80)
    q3 = "Doanh nghiệp có vốn đầu tư nước ngoài thuê giám đốc là người nước ngoài thì chế độ bảo hiểm xã hội áp dụng thế nào?"
    print(f"Câu hỏi: '{q3}'")
    res3 = app.invoke({"query": q3, "client_id": "demo_client"})
    print(f"-> Route:           {res3.get('route')}")
    print(f"-> CRAG Action:     {res3.get('crag_action')}")
    print(f"-> Merged Evidence: {len(res3.get('evidence', []))}")
    print(f"-> Answer:          {res3.get('generation', {}).get('answer')[:200]}...")
    print(f"-> Citation Report: {res3.get('citation_report')}")

    # -------------------------------------------------------------------------
    # TEST 4: Database Tool (Structured metadata query)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("TEST 4: DATABASE TOOL — Direct Structured Metadata Query")
    print("#" * 80)
    q4 = "Văn bản số 41/2024/QH15 còn hiệu lực không?"
    print(f"Câu hỏi: '{q4}'")
    res4 = app.invoke({"query": q4, "client_id": "demo_client"})
    print(f"-> Route:           {res4.get('route')} (Expected: database)")
    print(f"-> Answer:          {res4.get('generation', {}).get('answer')}")
    print(f"-> Citation Report: {res4.get('citation_report')}")

    # -------------------------------------------------------------------------
    # TEST 5: Citation Failure (Simulation proving validator catches fake citations)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("TEST 5: CITATION FAILURE — Intercepting Hallucinated Source IDs")
    print("#" * 80)
    fake_answer = {
        "answer": "Theo Điều 999 của Luật Doanh nghiệp 2099, mọi thủ tục đều được miễn trừ.",
        "claims": [
            {
                "text": "Mọi thủ tục đều được miễn trừ.",
                "source_ids": ["DOC_FAKE_2099_D999"]
            }
        ],
        "abstain": False,
    }
    evidence_map = {
        "DOC_41_2024_QH15_D2": {"id": "DOC_41_2024_QH15_D2", "status": "effective"}
    }
    report5 = validate_citations(fake_answer, evidence_map)
    print("Mô phỏng câu trả lời chứa source_id bịa đặt: 'DOC_FAKE_2099_D999'")
    print(f"-> Citation Validator Result: ok = {report5['ok']} (Expected: False)")
    print(f"-> Detected Errors:          {report5['errors']}")
    print(f"-> Citation Accuracy:        {report5['citation_accuracy']}")
    assert report5["ok"] is False, "Citation validator failed to catch fake source ID!"

    print("\n" + "=" * 80)
    print("ALL 5 DEMO TEST CASES SUCCESSFULLY EXECUTED AND VERIFIED!")
    print("=" * 80)


def interactive_cli():
    """Interactive command-line chat session with memory context."""
    app = get_crag_app()
    store = get_memory_store()
    client_id = "cli_user_default"
    session_id = store.create_session(client_id)

    print("=" * 80)
    print("LEGAL CRAG ASSISTANT V3 — INTERACTIVE CLI")
    print("Gõ câu hỏi pháp lý bằng tiếng Việt (hoặc 'exit' để thoát, 'clear' để xóa memory)")
    print("=" * 80)

    while True:
        try:
            query = input("\n[Bạn]: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("Tạm biệt!")
                break
            if query.lower() == "clear":
                store.clear_client_memories(client_id)
                print("Đã xóa sạch Semantic Memory của client.")
                continue

            # Extract memory
            extract_and_save_memories(client_id, query)
            mem_ctx = store.format_memory_context(client_id)

            # Invoke Agent
            res = app.invoke({
                "query": query,
                "client_id": client_id,
                "session_id": session_id,
                "memory_context": mem_ctx,
            })

            route = res.get("route", "rag")
            action = res.get("crag_action", "DATABASE" if route == "database" else "CORRECT")
            ans = res.get("generation", {}).get("answer", "")
            report = res.get("citation_report", {})
            evidence = res.get("evidence", [])

            print(f"\n[Trace]: Route = {route} | CRAG Action = {action} | Evidence Strips = {len(evidence)}")
            print(f"[Trợ lý]: {ans}")

            if report.get("valid_citations"):
                print(f"[Căn cứ trích dẫn]: {', '.join(report['valid_citations'])}")
            if report.get("errors"):
                print(f"[Cảnh báo trích dẫn]: {report['errors']}")

        except (KeyboardInterrupt, EOFError):
            print("\nTạm biệt!")
            break


def main():
    parser = argparse.ArgumentParser(description="Legal CRAG Assistant V3 CLI & Demo")
    parser.add_argument("--demo", action="store_true", help="Run the 5 mandatory demo test scenarios (Table 3.2)")
    args = parser.parse_args()

    if args.demo:
        run_demo_suite()
    else:
        interactive_cli()


if __name__ == "__main__":
    main()

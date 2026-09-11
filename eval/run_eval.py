"""Automated Benchmark and Calibration Runner for Legal CRAG Assistant V3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import get_crag_app, invoke_crag
from config import CALIBRATION_SET_PATH, TEST_SET_PATH
from eval.metrics import (
    compute_action_f1,
    compute_citation_metrics,
    compute_fallback_metrics,
    compute_mrr,
    compute_recall_at_k,
    compute_temporal_correctness,
)
from retrieval.bm25 import bm25_retrieve
from retrieval.dense import dense_retrieve
from retrieval.fusion import rrf_merge
from retrieval.reranker import decide_crag_action, rerank


def run_grid_search_calibration(
    calibration_path: Path | str = CALIBRATION_SET_PATH,
) -> List[Dict[str, Any]]:
    """Execute grid search calibration over (T_low, T_high) pairs on Calibration Set (Table 4.3)."""
    calibration_path = Path(calibration_path)
    with open(calibration_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    threshold_grid = [
        (0.20, 0.60),
        (0.25, 0.65),
        (0.30, 0.70),
        (0.35, 0.70),
        (0.35, 0.75),
        (0.40, 0.80),
    ]

    print("=" * 80)
    print("GRID SEARCH THRESHOLD CALIBRATION (20 SAMPLES)")
    print("=" * 80)
    print(f"{'T_low':<8} {'T_high':<8} {'Macro-F1':<12} {'Fallback Prec':<16} {'False Fallback':<16}")
    print("-" * 80)

    calibration_results = []

    for t_low, t_high in threshold_grid:
        records = []
        for s in samples:
            q = s["question"]
            exp_act = s["expected_action"]

            if s.get("type") == "database":
                pred_act = "DATABASE"
            else:
                dense_hits = dense_retrieve(q, top_k=10)
                bm25_hits = bm25_retrieve(q, top_k=10)
                fused = rrf_merge([dense_hits, bm25_hits], top_k=10)
                reranked = rerank(q, fused, top_k=5)
                scores = [d.get("score", 0.0) for d in reranked]
                pred_act = decide_crag_action(scores, t_low=t_low, t_high=t_high)

            records.append({
                "type": s.get("type"),
                "expected_action": exp_act,
                "predicted_action": pred_act,
            })

        f1_data = compute_action_f1(records)
        fb_data = compute_fallback_metrics(records)

        row = {
            "t_low": t_low,
            "t_high": t_high,
            "macro_f1": f1_data["macro_f1"],
            "fallback_precision": fb_data["fallback_precision"],
            "false_fallback_rate": fb_data["false_fallback_rate"],
        }
        calibration_results.append(row)
        print(f"{t_low:<8.2f} {t_high:<8.2f} {row['macro_f1']:<12.4f} {row['fallback_precision']:<16.4f} {row['false_fallback_rate']:<16.4f}")

    # Best threshold by highest F1 with lowest false fallback
    best = sorted(calibration_results, key=lambda x: (x["macro_f1"], -x["false_fallback_rate"]), reverse=True)[0]
    print("-" * 80)
    print(f"Optimal Threshold Selected: T_low = {best['t_low']:.2f}, T_high = {best['t_high']:.2f} (Macro-F1: {best['macro_f1']:.4f})\n")
    return calibration_results


def run_test_benchmark(
    test_set_path: Path | str = TEST_SET_PATH,
) -> Dict[str, Any]:
    """Execute full evaluation benchmark across Held-out Test Set (40 questions)."""
    test_set_path = Path(test_set_path)
    with open(test_set_path, "r", encoding="utf-8") as f:
        test_samples = json.load(f)

    app = get_crag_app()

    print("=" * 80)
    print(f"RUNNING EVALUATION ON HELD-OUT TEST SET ({len(test_samples)} QUESTIONS)")
    print("=" * 80)

    eval_records = []
    retrieval_recalls = []
    retrieval_mrrs = []

    for idx, s in enumerate(test_samples, start=1):
        q = s["question"]
        q_type = s.get("type")
        exp_act = s.get("expected_action")
        exp_sources = s.get("expected_source_ids", [])
        as_of_date = s.get("as_of_date")

        # Run through LangGraph
        res = invoke_crag(query=q, as_of_date=as_of_date, session_id=f"eval_thread_{idx}")

        route = res.get("route")
        pred_act = "DATABASE" if route == "database" else res.get("crag_action", "AMBIGUOUS")
        generation = res.get("generation", {})
        report = res.get("citation_report", {})
        evidence = res.get("evidence", [])

        # Retrieval metrics
        retrieved_ids = [e.get("strip_id") or e.get("locator") or e.get("evidence_id") for e in evidence if e]
        recall = compute_recall_at_k(retrieved_ids, exp_sources, k=5)
        mrr = compute_mrr(retrieved_ids, exp_sources)

        if exp_sources:
            retrieval_recalls.append(recall)
            retrieval_mrrs.append(mrr)

        record = {
            "id": s.get("id"),
            "question": q,
            "type": q_type,
            "expected_action": exp_act,
            "predicted_action": pred_act,
            "answer": generation.get("answer"),
            "citation_report": report,
            "as_of_date": as_of_date,
            "recall@5": recall,
            "mrr": mrr,
        }
        eval_records.append(record)
        print(f"[{idx:02d}/{len(test_samples)}] Type: {q_type:<10} | Action: {pred_act:<10} | Citations OK: {str(report.get('ok')):<5} | Q: {q[:45]}...")

    # Calculate aggregate metrics
    action_f1 = compute_action_f1(eval_records)
    fallback_metrics = compute_fallback_metrics(eval_records)
    citation_metrics = compute_citation_metrics(eval_records)
    temporal_correctness = compute_temporal_correctness(eval_records)
    avg_recall = sum(retrieval_recalls) / len(retrieval_recalls) if retrieval_recalls else 1.0
    avg_mrr = sum(retrieval_mrrs) / len(retrieval_mrrs) if retrieval_mrrs else 1.0

    print("\n" + "=" * 80)
    print("FINAL BENCHMARK SUMMARY (HELD-OUT TEST SET)")
    print("=" * 80)
    print(f"1. Retrieval Metrics:")
    print(f"   - Recall@5:                 {avg_recall:.4f}")
    print(f"   - MRR:                      {avg_mrr:.4f}")
    print(f"2. Routing & Fallback Metrics:")
    print(f"   - Action Macro-F1:          {action_f1['macro_f1']:.4f}")
    print(f"   - Fallback Precision:       {fallback_metrics['fallback_precision']:.4f}")
    print(f"   - Fallback Recall:          {fallback_metrics['fallback_recall']:.4f}")
    print(f"   - False Fallback Rate:      {fallback_metrics['false_fallback_rate']:.4f}")
    print(f"3. Legal Generation & Compliance Metrics:")
    print(f"   - Citation Accuracy:        {citation_metrics['citation_accuracy']:.4f}")
    print(f"   - Citation Coverage:        {citation_metrics['citation_coverage']:.4f}")
    print(f"   - Legal Temporal Correct:   {temporal_correctness:.4f}")
    print("=" * 80)

    # Save benchmark report
    summary_report = {
        "retrieval_recall_at_5": round(avg_recall, 4),
        "retrieval_mrr": round(avg_mrr, 4),
        "action_macro_f1": action_f1["macro_f1"],
        "fallback_precision": fallback_metrics["fallback_precision"],
        "fallback_recall": fallback_metrics["fallback_recall"],
        "false_fallback_rate": fallback_metrics["false_fallback_rate"],
        "citation_accuracy": citation_metrics["citation_accuracy"],
        "citation_coverage": citation_metrics["citation_coverage"],
        "legal_temporal_correctness": temporal_correctness,
        "sample_count": len(test_samples),
    }

    report_path = Path("eval") / "benchmark_report.json"
    report_path.write_text(json.dumps(summary_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved benchmark report to: {report_path.resolve()}\n")

    return summary_report


if __name__ == "__main__":
    run_grid_search_calibration()
    run_test_benchmark()

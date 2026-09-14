"""Comprehensive Evaluation Metrics for Legal CRAG Assistant (Chapter 4)."""
from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Set

from logging_config import get_logger

log = get_logger(__name__)


def compute_recall_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int = 5) -> float:
    """Compute Recall@K: proportion of expected source IDs found in top-K retrieved IDs."""
    if not expected_ids:
        return 1.0
    top_k_set = set(retrieved_ids[:k])
    # Check exact or prefix match
    hits = 0
    for exp in expected_ids:
        if any(ret.startswith(exp) or exp.startswith(ret) for ret in top_k_set):
            hits += 1
    return hits / len(expected_ids)


def compute_mrr(retrieved_ids: List[str], expected_ids: List[str]) -> float:
    """Compute Mean Reciprocal Rank (MRR): 1 / rank of first relevant candidate."""
    if not expected_ids:
        return 1.0
    for rank, ret in enumerate(retrieved_ids, start=1):
        if any(ret.startswith(exp) or exp.startswith(ret) for exp in expected_ids):
            return 1.0 / rank
    return 0.0


def compute_fallback_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute Fallback Precision, Fallback Recall, and False Fallback Rate (Formulas 4.1, 4.2, 4.3).

    - Fallback Precision = True Fallback / Total Fallback Triggered
    - Fallback Recall = True Fallback / Total Out-of-corpus Queries
    - False Fallback Rate = In-corpus wrongly triggered / Total In-corpus Queries
    """
    total_fallback_triggered = 0
    true_fallback = 0
    total_out_of_corpus = 0
    total_in_corpus = 0
    false_fallback = 0

    for rec in eval_records:
        q_type = rec.get("type", "")
        # Triggered fallback if action was INCORRECT or AMBIGUOUS (invoking web search)
        action = rec.get("predicted_action", "")
        triggered = action in ("INCORRECT", "AMBIGUOUS")

        if triggered:
            total_fallback_triggered += 1

        if q_type == "incorrect":
            total_out_of_corpus += 1
            if triggered:
                true_fallback += 1
        elif q_type == "correct":
            total_in_corpus += 1
            if triggered:
                false_fallback += 1

    precision = (true_fallback / total_fallback_triggered) if total_fallback_triggered > 0 else 1.0
    recall = (true_fallback / total_out_of_corpus) if total_out_of_corpus > 0 else 1.0
    false_rate = (false_fallback / total_in_corpus) if total_in_corpus > 0 else 0.0

    return {
        "fallback_precision": round(precision, 4),
        "fallback_recall": round(recall, 4),
        "false_fallback_rate": round(false_rate, 4),
        "total_fallback_triggered": total_fallback_triggered,
        "true_fallback": true_fallback,
        "false_fallback": false_fallback,
    }


def compute_action_f1(eval_records: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute Macro-F1 across routing and CRAG action decisions."""
    classes = ["CORRECT", "AMBIGUOUS", "INCORRECT", "DATABASE"]
    f1_scores = {}

    for c in classes:
        tp = 0
        fp = 0
        fn = 0
        for rec in eval_records:
            pred = rec.get("predicted_action", "").upper()
            exp = rec.get("expected_action", "").upper()

            if pred == c and exp == c:
                tp += 1
            elif pred == c and exp != c:
                fp += 1
            elif pred != c and exp == c:
                fn += 1

        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_scores[c] = round(f1, 4)

    macro_f1 = sum(f1_scores.values()) / len(f1_scores)
    return {
        "macro_f1": round(macro_f1, 4),
        "per_class_f1": f1_scores,
    }


def compute_citation_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute Citation Accuracy and Citation Coverage across evaluated responses."""
    accuracies = []
    coverages = []

    for rec in eval_records:
        report = rec.get("citation_report", {})
        if "citation_accuracy" in report:
            accuracies.append(report["citation_accuracy"])
        if "citation_coverage" in report:
            coverages.append(report["citation_coverage"])

    avg_acc = (sum(accuracies) / len(accuracies)) if accuracies else 1.0
    avg_cov = (sum(coverages) / len(coverages)) if coverages else 1.0

    return {
        "citation_accuracy": round(avg_acc, 4),
        "citation_coverage": round(avg_cov, 4),
    }


def compute_temporal_correctness(eval_records: List[Dict[str, Any]]) -> float:
    """Measure proportion of responses that respected legal temporal validity."""
    temporal_records = [r for r in eval_records if r.get("as_of_date") or r.get("type") == "temporal"]
    if not temporal_records:
        return 1.0

    correct_count = 0
    for r in temporal_records:
        # Check citation report: no expired document errors
        errors = r.get("citation_report", {}).get("errors", [])
        if not any("hết hiệu lực" in e.lower() or "không còn hiệu lực" in e.lower() for e in errors):
            correct_count += 1

    return round(correct_count / len(temporal_records), 4)


def _patch_ragas_vertexai_shim() -> None:
    """Work around a broken transitive import in `ragas` (as of 0.4.3).

    `ragas.llms.base` unconditionally imports
    `langchain_community.chat_models.vertexai.ChatVertexAI`, a shim module that
    was removed from `langchain-community` >=0.4 (the Vertex AI integration
    moved to the standalone `langchain-google-vertexai` package). Pulling in
    that whole Google Cloud SDK just to satisfy one dead import is not
    reasonable for an on-premise Vietnamese legal assistant. The class is only
    ever used in a static `isinstance()` allow-list
    (`MULTIPLE_COMPLETION_SUPPORTED`) inside ragas — never instantiated — so a
    harmless placeholder class is a safe, fully contained substitute.
    """
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401
        return  # already importable (a future langchain-community restored it)
    except ModuleNotFoundError:
        pass

    shim = types.ModuleType(module_name)

    class ChatVertexAI:  # placeholder — never instantiated, only isinstance-checked
        pass

    shim.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = shim


def compute_ragas_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute real RAGAS Faithfulness, Answer Relevancy, Context Precision, and
    Context Recall (Es et al., 2023 — https://arxiv.org/abs/2309.15217) via the
    `ragas` package, using the project's configured chat model and embeddings.

    Each `eval_records` entry needs `question`, `answer`, `contexts` (list of
    retrieved evidence text strings), and `ground_truth` populated. Records
    missing any of these (abstained turns, pure `general`/`database` routes
    with no retrieval) are skipped — RAGAS's metrics are undefined without a
    retrieved context and a reference answer to compare against.
    """
    empty: Dict[str, Any] = {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_precision": 0.0,
        "context_recall": 0.0,
        "sample_count": 0,
    }

    rows = [r for r in eval_records if r.get("answer") and r.get("contexts") and r.get("ground_truth")]
    if not rows:
        log.warning("RAGAS skipped: no eval records have contexts+ground_truth+answer populated")
        return empty

    from llm import get_chat_model, get_embeddings

    llm = get_chat_model()
    embeddings = get_embeddings()
    if llm is None or embeddings is None:
        log.warning("RAGAS skipped: no LLM/embeddings client configured")
        return empty

    _patch_ragas_vertexai_shim()
    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
    from ragas.run_config import RunConfig

    dataset = Dataset.from_dict({
        "user_input": [r["question"] for r in rows],
        "response": [r["answer"] for r in rows],
        "retrieved_contexts": [r["contexts"] for r in rows],
        "reference": [r["ground_truth"] for r in rows],
    })

    result = ragas_evaluate(
        dataset,
        metrics=[Faithfulness(), AnswerRelevancy(strictness=1), ContextPrecision(), ContextRecall()],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=2, timeout=60, max_retries=2),
        raise_exceptions=False,
    )

    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    aggregated = {
        name: round(sum(float(row.get(name, 0.0)) for row in result.scores) / len(result.scores), 4)
        for name in metric_names
    }
    aggregated["sample_count"] = len(rows)
    return aggregated

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
    """Compute Fallback Precision, Fallback Recall, and False Fallback Rate metrics."""
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
    classes = ["CORRECT", "AMBIGUOUS", "INCORRECT"]
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
    """Patch missing ChatVertexAI import shim in ragas without extra dependencies."""
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    shim = types.ModuleType(module_name)
    class ChatVertexAI:
        pass
    shim.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = shim

_patch_ragas_vertexai_shim()


def _math_faithfulness(answer: str, contexts: List[str]) -> float:
    """Calculate faithfulness based on sentence-level context verification."""
    import re
    if not answer or not contexts:
        return 0.0
    sents = [s.strip() for s in re.split(r'[.\n;]+', answer) if len(s.strip().split()) >= 3]
    if not sents:
        return 1.0
    combined_ctx = " ".join(contexts).lower()
    verified = 0
    for sent in sents:
        words = [w.lower() for w in sent.split() if len(w) > 3]
        if not words:
            verified += 1
            continue
        overlap = sum(1 for w in words if w in combined_ctx)
        if (overlap / len(words)) >= 0.45:
            verified += 1
    return round(verified / len(sents), 4)


def _math_context_precision(contexts: List[str], ground_truth: str) -> float:
    """Calculate rank-weighted context precision against ground truth."""
    import re
    if not contexts or not ground_truth:
        return 0.0
    gt_words = set(w.lower() for w in re.findall(r'\w+', ground_truth) if len(w) > 3)
    if not gt_words:
        return 1.0
    precisions = []
    hits = 0
    for rank, ctx in enumerate(contexts, 1):
        ctx_words = set(w.lower() for w in re.findall(r'\w+', ctx))
        overlap = len(gt_words.intersection(ctx_words))
        if overlap >= 2:
            hits += 1
            precisions.append(hits / rank)
    return round(sum(precisions) / len(precisions), 4) if precisions else 0.0


def _math_context_recall(contexts: List[str], ground_truth: str) -> float:
    """Calculate context recall by attributing ground truth clauses to contexts."""
    import re
    if not contexts or not ground_truth:
        return 0.0
    gt_sents = [s.strip() for s in re.split(r'[.\n;]+', ground_truth) if len(s.strip().split()) >= 3]
    if not gt_sents:
        return 1.0
    combined_ctx = " ".join(contexts).lower()
    covered = 0
    for s in gt_sents:
        words = [w.lower() for w in s.split() if len(w) > 3]
        if not words or (sum(1 for w in words if w in combined_ctx) / len(words) >= 0.4):
            covered += 1
    return round(covered / len(gt_sents), 4)


def _math_answer_relevancy(question: str, answer: str, embeddings: Any = None) -> float:
    """Calculate semantic answer relevancy using cosine embedding similarity."""
    import re
    if not question or not answer:
        return 0.0
    if embeddings is not None:
        try:
            import numpy as np
            v_q = np.array(embeddings.embed_query(question))
            v_a = np.array(embeddings.embed_query(answer[:1000]))
            norm_q = np.linalg.norm(v_q)
            norm_a = np.linalg.norm(v_a)
            if norm_q > 0 and norm_a > 0:
                sim = float(np.dot(v_q, v_a) / (norm_q * norm_a))
                return round(max(0.0, min(1.0, sim)), 4)
        except Exception:
            pass
    q_words = set(w.lower() for w in re.findall(r'\w+', question) if len(w) > 3)
    a_words = set(w.lower() for w in re.findall(r'\w+', answer) if len(w) > 3)
    if not q_words:
        return 1.0
    return round(len(q_words.intersection(a_words)) / len(q_words), 4)


def compute_ragas_metrics(eval_records: List[Dict[str, Any]], use_llm: bool = False) -> Dict[str, Any]:
    """Compute RAGAS metrics (Faithfulness, Answer Relevancy, Context Precision, Context Recall)."""
    empty: Dict[str, Any] = {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_precision": 0.0,
        "context_recall": 0.0,
        "sample_count": 0,
        "evaluation_mode": "empty",
    }

    rows = [r for r in eval_records if r.get("answer") and r.get("contexts") and r.get("ground_truth")]
    if not rows:
        log.warning("RAGAS skipped: no eval records have contexts+ground_truth+answer populated")
        return empty

    import math
    from llm import get_chat_model, get_embeddings
    embeddings = get_embeddings()

    # 1. Compute deterministic mathematical metrics for all rows
    math_faith = [_math_faithfulness(r["answer"], r["contexts"]) for r in rows]
    math_prec = [_math_context_precision(r["contexts"], r["ground_truth"]) for r in rows]
    math_rec = [_math_context_recall(r["contexts"], r["ground_truth"]) for r in rows]
    math_rel = [_math_answer_relevancy(r["question"], r["answer"], embeddings) for r in rows]

    ragas_scores: Dict[str, List[float]] = {
        "faithfulness": list(math_faith),
        "answer_relevancy": list(math_rel),
        "context_precision": list(math_prec),
        "context_recall": list(math_rec),
    }
    ragas_success = False

    # 2. If use_llm=True, attempt official Ragas evaluate with remote LLM
    if use_llm:
        llm = get_chat_model()
        if llm is not None and embeddings is not None:
            try:
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
                    run_config=RunConfig(max_workers=2, timeout=90, max_retries=2),
                    raise_exceptions=False,
                    show_progress=False,
                )
                for idx, row_score in enumerate(result.scores):
                    for m_name in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                        val = row_score.get(m_name)
                        if val is not None and not (isinstance(val, float) and math.isnan(val)):
                            ragas_scores[m_name][idx] = float(val)
                ragas_success = True
            except Exception as e:
                log.warning("Official Ragas evaluation encountered warning (%s) -> using mathematical metrics", e)

    aggregated = {
        name: round(sum(scores) / len(scores), 4) if scores else 0.0
        for name, scores in ragas_scores.items()
    }
    aggregated["sample_count"] = len(rows)
    aggregated["evaluation_mode"] = "ragas_llm" if ragas_success else "mathematical_grounded"
    return aggregated

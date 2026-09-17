"""Reranker Module with Cross-Encoder Scoring and Sigmoid Normalization."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from config import INTERNAL_STRIP_MIN, RERANKER_MODEL, T_HIGH, T_LOW, TOP_K_RERANK
from logging_config import get_logger, timed_stage

log = get_logger(__name__)


def sigmoid(x: float) -> float:
    """Sigmoid activation function to map arbitrary real logits to [0.0, 1.0]."""
    try:
        if x > 20:
            return 1.0
        elif x < -20:
            return 0.0
        return 1.0 / (1.0 + math.exp(-float(x)))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


class LegalReranker:
    """Manages cross-encoder model scoring with robust fallbacks."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self._model = None
        self._model_type = None
        self._init_model()

    def _init_model(self):
        # 1. Try FlagEmbedding
        try:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(self.model_name, use_fp16=False)
            self._model_type = "flag"
            log.info("Reranker model=%s -> real FlagReranker (cross-encoder) loaded", self.model_name)
            return
        except Exception as e:
            log.debug("Reranker FlagEmbedding unavailable (%s)", e)

        # 2. Try sentence_transformers CrossEncoder
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            self._model_type = "cross_encoder"
            log.info("Reranker model=%s -> real sentence-transformers CrossEncoder loaded", self.model_name)
            return
        except Exception as e:
            log.debug("Reranker sentence-transformers unavailable (%s)", e)

        # 3. Fallback to token-level semantic scorer
        self._model_type = "fallback"
        log.warning(
            "Reranker model=%s NOT available -> FALLBACK token-overlap heuristic in use (no real cross-encoder)",
            self.model_name,
        )

    def compute_scores(self, query: str, texts: List[str]) -> List[float]:
        """Compute sigmoid-normalized relevance scores in [0.0, 1.0]."""
        if not texts:
            return []

        if self._model_type == "flag":
            try:
                pairs = [[query, t] for t in texts]
                with timed_stage(log, "RETRIEVE:RERANK:MODEL_INFER", model_type=self._model_type, candidates=len(texts)):
                    raw = self._model.compute_score(pairs)
                if isinstance(raw, (int, float)):
                    raw = [raw]
                return [sigmoid(s) for s in raw]
            except Exception:
                pass

        elif self._model_type == "cross_encoder":
            try:
                pairs = [[query, t] for t in texts]
                with timed_stage(log, "RETRIEVE:RERANK:MODEL_INFER", model_type=self._model_type, candidates=len(texts)):
                    raw = self._model.predict(pairs)
                return [sigmoid(float(s)) for s in raw]
            except Exception:
                pass

        # Fallback heuristic: token overlap + exact match + length penalty
        return [self._fallback_score(query, t) for t in texts]

    def _fallback_score(self, query: str, text: str) -> float:
        """Heuristic cross-relevance scoring when transformer models are unavailable."""
        q_tokens = set(query.lower().split())
        t_tokens = set(text.lower().split())
        if not q_tokens or not t_tokens:
            return 0.1

        overlap = len(q_tokens.intersection(t_tokens))
        jaccard = overlap / len(q_tokens.union(t_tokens))
        recall = overlap / len(q_tokens)

        # Check exact key phrase match (e.g. "Điều 25", "thời gian thử việc", "tối đa")
        phrase_boost = 0.0
        q_lower = query.lower()
        t_lower = text.lower()
        for word in query.split():
            if len(word) > 3 and word.lower() in t_lower:
                phrase_boost += 0.15

        raw_logit = -2.0 + (recall * 4.0) + (jaccard * 3.0) + min(phrase_boost, 1.5)
        return sigmoid(raw_logit)


_GLOBAL_RERANKER: Optional[LegalReranker] = None


def get_reranker() -> LegalReranker:
    global _GLOBAL_RERANKER
    if _GLOBAL_RERANKER is None:
        _GLOBAL_RERANKER = LegalReranker()
    return _GLOBAL_RERANKER


def score_pairs(query: str, docs: List[Dict[str, Any]]) -> List[float]:
    """Score a list of document objects against a query."""
    reranker = get_reranker()
    texts = [d.get("text", "") for d in docs]
    return reranker.compute_scores(query, texts)


def rerank(
    query: str,
    docs: List[Dict[str, Any]],
    top_k: int = TOP_K_RERANK,
) -> List[Dict[str, Any]]:
    """Rerank candidate documents and attach normalized relevance scores.

    Returns
    -------
    list of dict
        Top-K reranked documents with 'score' attribute.
    """
    if not docs:
        return []

    scores = score_pairs(query, docs)
    scored_docs = []
    for doc, score in zip(docs, scores):
        d = doc.copy()
        d["score"] = float(score)
        d["relevance_score"] = float(score)
        scored_docs.append(d)

    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    return scored_docs[:top_k]


def decide_crag_action(scores: List[float], t_low: float = T_LOW, t_high: float = T_HIGH) -> str:
    """Decide CRAG routing action based on calibrated thresholds.

    Rules (Listing 3.11):
    - best_score >= T_HIGH -> 'CORRECT'
    - best_score <= T_LOW  -> 'INCORRECT'
    - otherwise            -> 'AMBIGUOUS'
    """
    best_score = max(scores) if scores else 0.0
    if best_score >= t_high:
        action = "CORRECT"
    elif best_score <= t_low:
        action = "INCORRECT"
    else:
        action = "AMBIGUOUS"
    log.info(
        "CRAG decision: best_score=%.4f (t_low=%.2f t_high=%.2f) scores=%s -> action=%s",
        best_score, t_low, t_high, [round(s, 3) for s in scores], action,
    )
    return action

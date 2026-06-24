"""
Eval runner — orchestrates scoring of a prompt version against a baseline.

Baseline is determined by:
  1. Dataset items labeled "good" (looked up by span_id in ClickHouse) — preferred
  2. Spans from a previous prompt_version in ClickHouse — fallback

The runner is synchronous and designed for small datasets (< 10k items).
Async worker pool is phase 2.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .scorers import DEFAULT_SCORERS

logger = logging.getLogger("trace_lit.eval")

Scorer = Callable[[list[dict[str, Any]], list[dict[str, Any]]], tuple[float, dict[str, Any]]]


@dataclass
class EvalResult:
    passed: bool
    score: float                        # 0.0–1.0, average across all scorers
    threshold: float
    new_spans: int
    baseline_spans: int
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


def run_eval(
    *,
    baseline_spans: list[dict[str, Any]],
    new_spans: list[dict[str, Any]],
    threshold: float = 0.8,
    scorers: list[Scorer] | None = None,
) -> EvalResult:
    """
    Score new_spans against baseline_spans.

    Args:
        baseline_spans: Spans representing known-good behaviour (from dataset or previous version).
        new_spans:      Spans for the prompt version under evaluation.
        threshold:      Minimum passing score (0.0–1.0). Default 0.8.
        scorers:        Override scorer list (defaults to DEFAULT_SCORERS).

    Returns:
        EvalResult with pass/fail, score, and per-scorer detail.
    """
    if scorers is None:
        scorers = DEFAULT_SCORERS

    if not new_spans:
        return EvalResult(
            passed=False,
            score=0.0,
            threshold=threshold,
            new_spans=0,
            baseline_spans=len(baseline_spans),
            message="No spans found for this prompt version — nothing to evaluate.",
        )

    if not baseline_spans:
        return EvalResult(
            passed=False,
            score=0.0,
            threshold=threshold,
            new_spans=len(new_spans),
            baseline_spans=0,
            message="No baseline available — add labeled examples to the dataset first.",
        )

    scores: list[float] = []
    detail: dict[str, Any] = {}

    for scorer in scorers:
        try:
            score, scorer_detail = scorer(baseline_spans, new_spans)
            scores.append(score)
            detail.update(scorer_detail)
        except Exception as exc:
            logger.warning("eval scorer %s failed: %s", scorer.__name__, exc)

    if not scores:
        return EvalResult(
            passed=False,
            score=0.0,
            threshold=threshold,
            new_spans=len(new_spans),
            baseline_spans=len(baseline_spans),
            message="All scorers failed — check logs.",
        )

    final_score = sum(scores) / len(scores)
    passed = final_score >= threshold

    message = _summarise(final_score, threshold, passed, detail)
    return EvalResult(
        passed=passed,
        score=round(final_score, 4),
        threshold=threshold,
        new_spans=len(new_spans),
        baseline_spans=len(baseline_spans),
        message=message,
        detail=detail,
    )


def _summarise(score: float, threshold: float, passed: bool, detail: dict[str, Any]) -> str:
    status = "PASSED" if passed else "FAILED"
    parts = [f"{status} — score {score:.2f} (threshold {threshold:.2f})"]

    err_base = detail.get("error_rate_base")
    err_new  = detail.get("error_rate_new")
    if err_base is not None and err_new is not None:
        delta = (err_new - err_base) * 100
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        parts.append(f"error rate {err_base*100:.1f}% {arrow} {err_new*100:.1f}%")

    cost_base = detail.get("cost_base")
    cost_new  = detail.get("cost_new")
    if cost_base is not None and cost_new is not None and cost_base > 0:
        pct = (cost_new - cost_base) / cost_base * 100
        arrow = "↑" if pct > 0 else ("↓" if pct < 0 else "→")
        parts.append(f"cost {arrow}{abs(pct):.0f}%")

    return " · ".join(parts)

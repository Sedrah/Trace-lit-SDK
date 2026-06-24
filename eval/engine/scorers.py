"""
Built-in scorers for the eval engine (free tier).

Each scorer takes baseline_spans and new_spans (lists of dicts from ClickHouse)
and returns a float 0.0–1.0 where 1.0 means the new version is at least as
good as baseline on that dimension.

Scores are averaged across all active scorers to produce the final score.
"""
from __future__ import annotations

from typing import Any


def _avg(spans: list[dict[str, Any]], key: str) -> float:
    vals = [float(s.get(key) or 0) for s in spans]
    return sum(vals) / len(vals) if vals else 0.0


def error_rate_scorer(
    baseline: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Score based on change in error rate. Degradation is penalised more than improvement."""
    base_rate = sum(1 for s in baseline if s.get("status") == "error") / max(len(baseline), 1)
    new_rate  = sum(1 for s in new      if s.get("status") == "error") / max(len(new), 1)

    if base_rate == 0:
        # Baseline had no errors — any errors in new version are a regression
        score = 1.0 if new_rate == 0 else max(0.0, 1.0 - new_rate * 5)
    else:
        # Allow up to 10% relative increase before penalising
        ratio = new_rate / base_rate
        score = 1.0 if ratio <= 1.1 else max(0.0, 1.0 - (ratio - 1.0))

    return score, {"error_rate_base": base_rate, "error_rate_new": new_rate}


def cost_scorer(
    baseline: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Score based on change in average cost. Up to 20% increase is acceptable."""
    base_cost = _avg(baseline, "cost_usd")
    new_cost  = _avg(new,      "cost_usd")

    if base_cost == 0:
        score = 1.0  # no cost baseline — can't penalise
    else:
        ratio = new_cost / base_cost
        score = 1.0 if ratio <= 1.2 else max(0.0, 1.0 - (ratio - 1.2))

    return score, {"cost_base": base_cost, "cost_new": new_cost}


def duration_scorer(
    baseline: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Score based on change in average duration. Up to 30% increase is acceptable."""
    base_dur = _avg(baseline, "duration_ms")
    new_dur  = _avg(new,      "duration_ms")

    if base_dur == 0:
        score = 1.0
    else:
        ratio = new_dur / base_dur
        score = 1.0 if ratio <= 1.3 else max(0.0, 1.0 - (ratio - 1.3) * 2)

    return score, {"duration_base": base_dur, "duration_new": new_dur}


# ---------------------------------------------------------------------------
# Enterprise seam — LLM-as-judge replaces or augments built-in scorers
# ---------------------------------------------------------------------------

try:
    from trace_lit_enterprise.eval_judge import llm_judge_scorer  # type: ignore[import]
    EXTRA_SCORERS = [llm_judge_scorer]
except ImportError:
    EXTRA_SCORERS = []

DEFAULT_SCORERS = [error_rate_scorer, cost_scorer, duration_scorer] + EXTRA_SCORERS

"""
Model pricing table and cost calculation.

Prices are in USD per 1M tokens. The table covers the most common models used
with LangChain, LangGraph, and CrewAI. All values are configurable via the
TRACELIT_MODEL_PRICING env var (JSON override).

Format of override:
    TRACELIT_MODEL_PRICING='{"gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.0}}'
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("trace_lit.pipeline")


@dataclass(frozen=True)
class ModelPricing:
    input_per_1m: float   # USD per 1M input tokens
    output_per_1m: float  # USD per 1M output tokens


# ---------------------------------------------------------------------------
# Default pricing table (as of early 2026 — update via TRACELIT_MODEL_PRICING)
# ---------------------------------------------------------------------------

_DEFAULT_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4o":                      ModelPricing(input_per_1m=2.50,  output_per_1m=10.00),
    "gpt-4o-mini":                 ModelPricing(input_per_1m=0.15,  output_per_1m=0.60),
    "gpt-4o-2024-11-20":           ModelPricing(input_per_1m=2.50,  output_per_1m=10.00),
    "gpt-4-turbo":                 ModelPricing(input_per_1m=10.00, output_per_1m=30.00),
    "gpt-4-turbo-preview":         ModelPricing(input_per_1m=10.00, output_per_1m=30.00),
    "gpt-4":                       ModelPricing(input_per_1m=30.00, output_per_1m=60.00),
    "gpt-3.5-turbo":               ModelPricing(input_per_1m=0.50,  output_per_1m=1.50),
    "o1":                          ModelPricing(input_per_1m=15.00, output_per_1m=60.00),
    "o1-mini":                     ModelPricing(input_per_1m=3.00,  output_per_1m=12.00),
    "o3-mini":                     ModelPricing(input_per_1m=1.10,  output_per_1m=4.40),

    # Anthropic
    "claude-opus-4-6":             ModelPricing(input_per_1m=15.00, output_per_1m=75.00),
    "claude-sonnet-4-6":           ModelPricing(input_per_1m=3.00,  output_per_1m=15.00),
    "claude-haiku-4-5-20251001":   ModelPricing(input_per_1m=0.80,  output_per_1m=4.00),
    "claude-3-5-sonnet-20241022":  ModelPricing(input_per_1m=3.00,  output_per_1m=15.00),
    "claude-3-5-haiku-20241022":   ModelPricing(input_per_1m=0.80,  output_per_1m=4.00),
    "claude-3-opus-20240229":      ModelPricing(input_per_1m=15.00, output_per_1m=75.00),
    "claude-3-sonnet-20240229":    ModelPricing(input_per_1m=3.00,  output_per_1m=15.00),
    "claude-3-haiku-20240307":     ModelPricing(input_per_1m=0.25,  output_per_1m=1.25),

    # Google
    "gemini-1.5-pro":              ModelPricing(input_per_1m=1.25,  output_per_1m=5.00),
    "gemini-1.5-flash":            ModelPricing(input_per_1m=0.075, output_per_1m=0.30),
    "gemini-2.0-flash":            ModelPricing(input_per_1m=0.10,  output_per_1m=0.40),

    # Mistral
    "mistral-large-latest":        ModelPricing(input_per_1m=2.00,  output_per_1m=6.00),
    "mistral-small-latest":        ModelPricing(input_per_1m=0.20,  output_per_1m=0.60),

    # Meta (via APIs)
    "llama-3.3-70b-versatile":     ModelPricing(input_per_1m=0.59,  output_per_1m=0.79),
    "llama-3.1-8b-instant":        ModelPricing(input_per_1m=0.05,  output_per_1m=0.08),
}


def _load_pricing() -> dict[str, ModelPricing]:
    """Load the pricing table, applying any TRACELIT_MODEL_PRICING overrides from env."""
    pricing = dict(_DEFAULT_PRICING)
    override_json = os.getenv("TRACELIT_MODEL_PRICING", "")
    if override_json:
        try:
            overrides = json.loads(override_json)
            for model, prices in overrides.items():
                pricing[model] = ModelPricing(
                    input_per_1m=float(prices["input_per_1m"]),
                    output_per_1m=float(prices["output_per_1m"]),
                )
        except Exception as exc:
            logger.warning("AMO: failed to parse TRACELIT_MODEL_PRICING override: %s", exc)
    return pricing


# Module-level singleton — loaded once at import time
PRICING: dict[str, ModelPricing] = _load_pricing()


def calculate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost in USD for a model call.

    Returns 0.0 if the model is unknown or tokens are zero.
    Unknown models are logged at DEBUG level so operators can add pricing entries.
    """
    if not model or (input_tokens == 0 and output_tokens == 0):
        return 0.0

    pricing = PRICING.get(model)
    if pricing is None:
        # Try a prefix match — e.g. "gpt-4o-2024-08-06" → "gpt-4o"
        for key in PRICING:
            if model.startswith(key):
                pricing = PRICING[key]
                break

    if pricing is None:
        logger.debug("AMO: no pricing for model %r — cost will be 0.0", model)
        return 0.0

    cost = (input_tokens / 1_000_000) * pricing.input_per_1m
    cost += (output_tokens / 1_000_000) * pricing.output_per_1m
    return round(cost, 8)

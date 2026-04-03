from __future__ import annotations

import pytest
from pipeline.cost import calculate_cost, ModelPricing, PRICING


def test_known_model_cost() -> None:
    cost = calculate_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    # $2.50 input + $10.00 output = $12.50
    assert cost == pytest.approx(12.50, rel=1e-4)


def test_cheap_model_small_call() -> None:
    cost = calculate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
    # (1000/1M)*0.15 + (500/1M)*0.60 = 0.00015 + 0.0003 = 0.00045
    assert cost == pytest.approx(0.00045, rel=1e-4)


def test_anthropic_model() -> None:
    cost = calculate_cost("claude-sonnet-4-6", input_tokens=500_000, output_tokens=500_000)
    # (0.5 * 3.00) + (0.5 * 15.00) = 1.50 + 7.50 = 9.00
    assert cost == pytest.approx(9.00, rel=1e-4)


def test_zero_tokens_returns_zero() -> None:
    assert calculate_cost("gpt-4o", input_tokens=0, output_tokens=0) == 0.0


def test_none_model_returns_zero() -> None:
    assert calculate_cost(None, input_tokens=100, output_tokens=100) == 0.0


def test_unknown_model_returns_zero() -> None:
    cost = calculate_cost("unknown-model-xyz", input_tokens=100, output_tokens=100)
    assert cost == 0.0


def test_prefix_match() -> None:
    # "gpt-4o-2024-08-06" should match "gpt-4o" via prefix
    cost_exact = calculate_cost("gpt-4o", input_tokens=1000, output_tokens=1000)
    cost_versioned = calculate_cost("gpt-4o-2024-08-06", input_tokens=1000, output_tokens=1000)
    assert cost_exact == cost_versioned


def test_all_pricing_entries_have_positive_values() -> None:
    for model, pricing in PRICING.items():
        assert pricing.input_per_1m > 0, f"{model} has non-positive input price"
        assert pricing.output_per_1m > 0, f"{model} has non-positive output price"

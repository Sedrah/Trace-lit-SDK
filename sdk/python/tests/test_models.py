"""Tests for TraceEvent and supporting models."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from amo.models import ErrorDetail, TraceEvent


def test_trace_event_defaults() -> None:
    event = TraceEvent(agent_name="bot", action="run")
    assert event.org_id == "default"
    assert isinstance(event.trace_id, UUID)
    assert isinstance(event.span_id, UUID)
    assert event.parent_span_id is None
    assert event.framework == "raw"
    assert event.status == "success"
    assert event.duration_ms == 0
    assert event.input_tokens == 0
    assert event.output_tokens == 0
    assert event.cost_usd == 0.0
    assert event.model is None
    assert event.error is None
    assert event.metadata == {}


def test_trace_event_is_immutable() -> None:
    event = TraceEvent(agent_name="bot", action="run")
    with pytest.raises(Exception):
        event.status = "error"  # type: ignore[misc]


def test_trace_event_model_copy_update() -> None:
    event = TraceEvent(agent_name="bot", action="run")
    updated = event.model_copy(update={"status": "error", "duration_ms": 42})
    assert updated.status == "error"
    assert updated.duration_ms == 42
    # Original unchanged
    assert event.status == "success"
    assert event.duration_ms == 0


def test_trace_event_parent_span() -> None:
    parent = TraceEvent(agent_name="parent", action="outer")
    child = TraceEvent(
        agent_name="child",
        action="inner",
        trace_id=parent.trace_id,
        parent_span_id=parent.span_id,
    )
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id


def test_trace_event_kafka_payload_roundtrip() -> None:
    event = TraceEvent(
        agent_name="bot",
        action="run",
        input_tokens=100,
        output_tokens=50,
        model="gpt-4o",
    )
    payload = event.to_kafka_payload()
    assert isinstance(payload, bytes)
    data = json.loads(payload)
    assert data["agent_name"] == "bot"
    assert data["input_tokens"] == 100
    assert data["model"] == "gpt-4o"
    # api_key must NOT appear in the payload
    assert "api_key" not in data


def test_error_detail() -> None:
    err = ErrorDetail(error_type="ValueError", message="bad input", traceback="...")
    assert err.error_type == "ValueError"
    assert err.traceback == "..."


def test_trace_event_with_error() -> None:
    event = TraceEvent(
        agent_name="bot",
        action="run",
        status="error",
        error=ErrorDetail(error_type="RuntimeError", message="oops"),
    )
    assert event.status == "error"
    assert event.error is not None
    assert event.error.error_type == "RuntimeError"


def test_trace_event_invalid_framework() -> None:
    with pytest.raises(ValidationError):
        TraceEvent(agent_name="bot", action="run", framework="unknown")  # type: ignore[arg-type]


def test_trace_event_invalid_status() -> None:
    with pytest.raises(ValidationError):
        TraceEvent(agent_name="bot", action="run", status="pending")  # type: ignore[arg-type]

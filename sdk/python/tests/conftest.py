"""Shared fixtures for the AMO SDK test suite."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

import trace_lit
from trace_lit.emitter import BaseEmitter, reset_emitter
from trace_lit.models import TraceEvent


class CapturingEmitter(BaseEmitter):
    """Test emitter that collects all emitted events in memory."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()


@pytest.fixture()
def capturing_emitter() -> Iterator[CapturingEmitter]:
    """
    Replaces the global emitter with a CapturingEmitter for the duration of the test.
    Restores the original emitter (None → lazy reinit) on teardown.
    """
    emitter = CapturingEmitter()
    reset_emitter(emitter)
    yield emitter
    reset_emitter(None)


@pytest.fixture(autouse=True)
def reset_config() -> Iterator[None]:
    """Reset SDK config to a deterministic test state before each test."""
    amo.configure(backend="noop", disabled=False, sampling_rate=1.0)
    yield
    # Leave state clean for the next test
    amo.configure(backend="noop", disabled=False, sampling_rate=1.0)

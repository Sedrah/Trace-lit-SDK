"""Tests for the @trace decorator — sync, async, nesting, errors, sampling."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

import trace_lit
from trace_lit.context import get_current_span_id, get_current_trace_id
from trace_lit.emitter import reset_emitter
from tests.conftest import CapturingEmitter


# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------

def test_trace_sync_success(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    def add(a: int, b: int) -> int:
        return a + b

    result = add(1, 2)
    assert result == 3
    assert len(capturing_emitter.events) == 1
    event = capturing_emitter.events[0]
    assert event.status == "success"
    assert event.duration_ms >= 0
    assert event.framework == "raw"


def test_trace_sync_exception(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    def boom() -> None:
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        boom()

    assert len(capturing_emitter.events) == 1
    event = capturing_emitter.events[0]
    assert event.status == "error"
    assert event.error is not None
    assert event.error.error_type == "ValueError"
    assert event.error.message == "test error"


def test_trace_with_labels(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace(agent_name="researcher", action="web_search", framework="raw")
    def search(query: str) -> list[str]:
        return [query]

    search("AI news")
    event = capturing_emitter.events[0]
    assert event.agent_name == "researcher"
    assert event.action == "web_search"


# ---------------------------------------------------------------------------
# Async functions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trace_async_success(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    async def async_add(a: int, b: int) -> int:
        return a + b

    result = await async_add(3, 4)
    assert result == 7
    assert len(capturing_emitter.events) == 1
    assert capturing_emitter.events[0].status == "success"


@pytest.mark.asyncio
async def test_trace_async_exception(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    async def async_boom() -> None:
        raise RuntimeError("async error")

    with pytest.raises(RuntimeError, match="async error"):
        await async_boom()

    event = capturing_emitter.events[0]
    assert event.status == "error"
    assert event.error is not None
    assert event.error.error_type == "RuntimeError"


# ---------------------------------------------------------------------------
# Context propagation — nested spans
# ---------------------------------------------------------------------------

def test_nested_spans_parent_child(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace(agent_name="outer", action="outer_action")
    def outer() -> None:
        inner()

    @amo.trace(agent_name="inner", action="inner_action")
    def inner() -> None:
        pass

    outer()

    assert len(capturing_emitter.events) == 2
    # inner emits first (LIFO because finally runs on return)
    inner_event = next(e for e in capturing_emitter.events if e.agent_name == "inner")
    outer_event = next(e for e in capturing_emitter.events if e.agent_name == "outer")

    assert inner_event.parent_span_id == outer_event.span_id
    assert inner_event.trace_id == outer_event.trace_id


def test_nested_spans_same_trace_id(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    def level1() -> None:
        level2()

    @amo.trace
    def level2() -> None:
        level3()

    @amo.trace
    def level3() -> None:
        pass

    level1()
    assert len(capturing_emitter.events) == 3
    trace_ids = {e.trace_id for e in capturing_emitter.events}
    assert len(trace_ids) == 1, "All spans in a call tree must share one trace_id"


def test_context_restored_after_exception(capturing_emitter: CapturingEmitter) -> None:
    """Context vars must be restored even when the function raises."""
    @amo.trace
    def failing() -> None:
        raise ValueError("fail")

    trace_id_before = get_current_trace_id()
    span_id_before = get_current_span_id()

    with pytest.raises(ValueError):
        failing()

    assert get_current_trace_id() == trace_id_before
    assert get_current_span_id() == span_id_before


# ---------------------------------------------------------------------------
# Concurrent async tasks — context isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_tasks_isolated_trace_ids(capturing_emitter: CapturingEmitter) -> None:
    """Two concurrent asyncio tasks must not share trace IDs."""

    @amo.trace
    async def task(name: str) -> str:
        await asyncio.sleep(0)  # yield to the event loop
        return name

    await asyncio.gather(task("a"), task("b"))

    assert len(capturing_emitter.events) == 2
    trace_ids = {e.trace_id for e in capturing_emitter.events}
    # Each top-level task gets its own trace_id
    assert len(trace_ids) == 2


# ---------------------------------------------------------------------------
# Disabled and sampling
# ---------------------------------------------------------------------------

def test_disabled_emits_nothing(capturing_emitter: CapturingEmitter) -> None:
    amo.configure(disabled=True)
    reset_emitter(capturing_emitter)

    @amo.trace
    def noop() -> int:
        return 42

    assert noop() == 42
    assert len(capturing_emitter.events) == 0


def test_sampling_rate_zero_emits_nothing(capturing_emitter: CapturingEmitter) -> None:
    amo.configure(sampling_rate=0.0)
    reset_emitter(capturing_emitter)

    @amo.trace
    def noop() -> int:
        return 99

    # Call many times — at rate=0.0 nothing should be emitted
    for _ in range(20):
        noop()

    assert len(capturing_emitter.events) == 0


def test_sampling_rate_full_emits_all(capturing_emitter: CapturingEmitter) -> None:
    amo.configure(sampling_rate=1.0)
    reset_emitter(capturing_emitter)

    @amo.trace
    def noop() -> None:
        pass

    for _ in range(5):
        noop()

    assert len(capturing_emitter.events) == 5


# ---------------------------------------------------------------------------
# Return value is always preserved
# ---------------------------------------------------------------------------

def test_return_value_preserved(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    def compute() -> dict[str, int]:
        return {"answer": 42}

    assert compute() == {"answer": 42}


@pytest.mark.asyncio
async def test_async_return_value_preserved(capturing_emitter: CapturingEmitter) -> None:
    @amo.trace
    async def compute() -> list[int]:
        return [1, 2, 3]

    assert await compute() == [1, 2, 3]

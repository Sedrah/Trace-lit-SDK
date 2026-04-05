"""Tests for emitter backends and the batching logic."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from trace_lit.emitter import (
    ConsoleEmitter,
    KafkaEmitter,
    NoopEmitter,
    _BatchingEmitter,
    _create_emitter,
)
from trace_lit.models import TraceEvent


def _make_event(**kwargs: object) -> TraceEvent:
    return TraceEvent(agent_name="test", action="test", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NoopEmitter
# ---------------------------------------------------------------------------

def test_noop_emitter_accepts_events() -> None:
    emitter = NoopEmitter()
    emitter.emit(_make_event())
    emitter.flush()
    emitter.close()  # should not raise


# ---------------------------------------------------------------------------
# ConsoleEmitter
# ---------------------------------------------------------------------------

def test_console_emitter_prints(capsys: pytest.CaptureFixture[str]) -> None:
    emitter = ConsoleEmitter()
    emitter.emit(_make_event())
    captured = capsys.readouterr()
    assert "agent_name" in captured.out
    assert "test" in captured.out


# ---------------------------------------------------------------------------
# Batching emitter — batch accumulation
# ---------------------------------------------------------------------------

class _CollectingEmitter(_BatchingEmitter):
    """Test subclass that captures published batches."""

    def __init__(self, batch_size: int = 10, flush_interval_ms: int = 200) -> None:
        self.batches: list[list[TraceEvent]] = []
        super().__init__(batch_size=batch_size, flush_interval_ms=flush_interval_ms)

    def _publish_batch(self, batch: list[TraceEvent]) -> None:
        self.batches.append(list(batch))


def test_batching_flushes_on_size() -> None:
    emitter = _CollectingEmitter(batch_size=3, flush_interval_ms=5000)
    for _ in range(3):
        emitter.emit(_make_event())
    # Give the background thread time to flush
    time.sleep(0.1)
    assert any(len(b) == 3 for b in emitter.batches)
    emitter.close()


def test_batching_flushes_on_interval() -> None:
    emitter = _CollectingEmitter(batch_size=100, flush_interval_ms=100)
    emitter.emit(_make_event())
    # Wait longer than flush_interval_ms
    time.sleep(0.4)
    assert len(emitter.batches) >= 1
    assert emitter.batches[0][0].agent_name == "test"
    emitter.close()


def test_batching_close_flushes_remaining() -> None:
    emitter = _CollectingEmitter(batch_size=100, flush_interval_ms=5000)
    for _ in range(5):
        emitter.emit(_make_event())
    emitter.close()
    total = sum(len(b) for b in emitter.batches)
    assert total == 5


# ---------------------------------------------------------------------------
# Retry on publish failure
# ---------------------------------------------------------------------------

def test_safe_publish_retries_and_drops(capsys: pytest.CaptureFixture[str]) -> None:
    call_count = 0

    class _FailingEmitter(_BatchingEmitter):
        def _publish_batch(self, batch: list[TraceEvent]) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("kafka down")

    import logging
    logging.getLogger("trace_lit").setLevel("WARNING")

    emitter = _FailingEmitter(batch_size=1, flush_interval_ms=50)
    emitter.emit(_make_event())
    time.sleep(0.5)
    emitter.close()
    # Should have retried 3× total (1 initial + 2 retries)
    assert call_count == 3


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def test_create_emitter_noop_when_disabled() -> None:
    from trace_lit.config import Config
    cfg = Config(disabled=True)
    emitter = _create_emitter(cfg)
    assert isinstance(emitter, NoopEmitter)


def test_create_emitter_noop_backend() -> None:
    from trace_lit.config import Config
    cfg = Config(backend="noop")
    emitter = _create_emitter(cfg)
    assert isinstance(emitter, NoopEmitter)


def test_create_emitter_console_backend() -> None:
    from trace_lit.config import Config
    cfg = Config(backend="console")
    emitter = _create_emitter(cfg)
    assert isinstance(emitter, ConsoleEmitter)


def test_create_emitter_kafka_missing_dep() -> None:
    """KafkaEmitter should raise a clear ImportError if confluent-kafka is not installed."""
    from trace_lit.config import Config
    cfg = Config(backend="kafka", api_key="test-key")

    with patch.dict("sys.modules", {"confluent_kafka": None}):
        with pytest.raises(ImportError, match="confluent-kafka"):
            _create_emitter(cfg)

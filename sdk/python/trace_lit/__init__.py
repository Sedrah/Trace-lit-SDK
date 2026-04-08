"""
AMO SDK — Agent Monitoring & Observability

Quick start::

    import trace_lit

    amo.configure(api_key="your-key", backend="console")  # console for dev, kafka for prod

    @amo.trace
    def my_agent(input: str) -> str:
        ...

    # Or with explicit labels:
    @amo.trace(agent_name="researcher", action="web_search")
    async def search(query: str) -> list[str]:
        ...
"""

from __future__ import annotations

import atexit
import logging
from typing import Any

from .config import Config, _set_config, get_config
from .context import get_current_trace_id
from .decorators import trace
from .emitter import _create_emitter, get_emitter, reset_emitter

# Registered once; subsequent configure() calls reuse the same handler because
# get_emitter() always returns the current singleton at exit time.
_atexit_registered = False

__all__ = ["configure", "trace", "get_current_trace_id"]

__version__ = "0.1.1"


def configure(
    *,
    api_key: str | None = None,
    backend: str | None = None,
    kafka_brokers: list[str] | None = None,
    endpoint: str | None = None,  # convenience alias for a single kafka broker
    kafka_topic: str | None = None,
    batch_size: int | None = None,
    flush_interval_ms: int | None = None,
    sampling_rate: float | None = None,
    log_level: str | None = None,
    disabled: bool | None = None,
) -> None:
    """
    Configure the AMO SDK. Call once at application startup before any @trace decorators fire.

    Args:
        api_key: Your AMO API key. Used by the ingestion pipeline to resolve your org.
        backend: 'kafka' (default, production), 'console' (dev/debug), or 'noop' (disabled).
        kafka_brokers: List of Kafka broker addresses. Defaults to ['localhost:9092'].
        endpoint: Convenience alias for a single Kafka broker (overrides kafka_brokers).
        kafka_topic: Kafka topic name. Defaults to 'trace_lit.spans.raw'.
        batch_size: Max events per batch before flushing. Defaults to 100.
        flush_interval_ms: Max ms to wait before flushing a partial batch. Defaults to 500.
        sampling_rate: Fraction of spans to emit (0.0–1.0). Defaults to 1.0 (all).
        log_level: Python logging level for the 'trace_lit' logger. Defaults to 'WARNING'.
        disabled: Set True to make all tracing a no-op. Also controlled by TRACELIT_DISABLED env var.

    Example::

        amo.configure(api_key="sk-...", backend="console")  # local dev
        amo.configure(api_key="sk-...", kafka_brokers=["kafka:9092"])  # production
    """
    current = get_config()

    # Build kwargs dict from non-None args
    updates: dict[str, Any] = {}
    if api_key is not None:
        updates["api_key"] = api_key
    if backend is not None:
        updates["backend"] = backend
    if endpoint is not None:
        updates["kafka_brokers"] = [endpoint]
    if kafka_brokers is not None:
        # Guard against a bare string — "host:9092" would be iterated char-by-char otherwise
        if isinstance(kafka_brokers, str):
            kafka_brokers = [kafka_brokers]
        updates["kafka_brokers"] = kafka_brokers
    if kafka_topic is not None:
        updates["kafka_topic"] = kafka_topic
    if batch_size is not None:
        updates["batch_size"] = batch_size
    if flush_interval_ms is not None:
        updates["flush_interval_ms"] = flush_interval_ms
    if sampling_rate is not None:
        updates["sampling_rate"] = sampling_rate
    if log_level is not None:
        updates["log_level"] = log_level
    if disabled is not None:
        updates["disabled"] = disabled

    # Build new frozen config from current + overrides
    new_config = Config(
        api_key=updates.get("api_key", current.api_key),
        backend=updates.get("backend", current.backend),  # type: ignore[arg-type]
        kafka_brokers=updates.get("kafka_brokers", current.kafka_brokers),
        kafka_topic=updates.get("kafka_topic", current.kafka_topic),
        batch_size=updates.get("batch_size", current.batch_size),
        flush_interval_ms=updates.get("flush_interval_ms", current.flush_interval_ms),
        sampling_rate=updates.get("sampling_rate", current.sampling_rate),
        log_level=updates.get("log_level", current.log_level),
        disabled=updates.get("disabled", current.disabled),
    )

    _set_config(new_config)

    # Apply log level to the amo logger
    logging.getLogger("trace_lit").setLevel(new_config.log_level)

    # Replace the emitter with one matching the new config
    reset_emitter(_create_emitter(new_config))

    # Drain the queue before the process exits — the background thread is a
    # daemon thread so Python would kill it without flushing on a short script.
    # Registered once; the handler always closes the current singleton so
    # subsequent configure() calls are covered without double-registering.
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(lambda: get_emitter().close())
        _atexit_registered = True

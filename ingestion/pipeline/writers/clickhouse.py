"""
ClickHouse batch writer for spans.

Buffers events in memory and flushes to ClickHouse either when the batch
reaches clickhouse_batch_size or when clickhouse_flush_interval_s elapses.
A background thread drives the time-based flush.

The writer is not thread-safe for concurrent write() calls — it is called
from a single ingestion worker thread. flush() is safe to call from any thread.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from trace_lit.models import TraceEvent

if TYPE_CHECKING:
    from ..config import PipelineConfig

logger = logging.getLogger("trace_lit.pipeline")

# Column order must match the CREATE TABLE in storage/clickhouse/migrations/001_initial.sql
_COLUMNS = [
    "org_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "timestamp",
    "framework",
    "agent_name",
    "action",
    "status",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "model",
    "error_type",
    "error_msg",
    "metadata",
    "prompt_name",
    "prompt_hash",
    "prompt_version",
    "input_text",
    "output_text",
]


def _event_to_row(event: TraceEvent) -> list[Any]:
    return [
        event.org_id,
        str(event.trace_id),
        str(event.span_id),
        str(event.parent_span_id) if event.parent_span_id else None,
        event.timestamp,
        event.framework,
        event.agent_name,
        event.action,
        event.status,
        event.duration_ms,
        event.input_tokens,
        event.output_tokens,
        event.cost_usd,
        event.model or "",
        event.error.error_type if event.error else "",
        event.error.message if event.error else "",
        event.model_dump_json(include={"metadata"}).replace('{"metadata":', "").rstrip("}"),
        event.prompt_name,
        event.prompt_hash,
        event.prompt_version,
        event.input_text,
        event.output_text,
    ]


class ClickHouseWriter:
    def __init__(self, config: PipelineConfig) -> None:
        import clickhouse_connect  # type: ignore[import]

        self._client = clickhouse_connect.get_client(
            host=config.clickhouse_host,
            port=config.clickhouse_port,
            database=config.clickhouse_database,
            username=config.clickhouse_user,
            password=config.clickhouse_password,
        )
        self._batch_size = config.clickhouse_batch_size
        self._flush_interval_s = config.clickhouse_flush_interval_s
        self._buffer: list[TraceEvent] = []
        self._lock = threading.Lock()

        # Background flush thread
        self._timer = threading.Timer(self._flush_interval_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def write(self, event: TraceEvent) -> None:
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self._batch_size:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def close(self) -> None:
        self._timer.cancel()
        self.flush()

    def _timer_flush(self) -> None:
        self.flush()
        # Reschedule
        self._timer = threading.Timer(self._flush_interval_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush_locked(self) -> None:
        """Must be called with self._lock held."""
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            rows = [_event_to_row(e) for e in batch]
            self._client.insert("spans", rows, column_names=_COLUMNS)
            logger.debug("AMO ClickHouse: inserted %d spans", len(rows))
        except Exception as exc:
            logger.error("AMO ClickHouse: insert failed (%d spans): %s", len(batch), exc)
            # Re-add to buffer for retry on next flush
            self._buffer[:0] = batch

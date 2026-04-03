"""
TimescaleDB metrics writer.

Converts each TraceEvent into metric rows in the agent_metrics hypertable.
Rows are buffered and flushed in batches.

Each span produces up to 4 metric rows:
  - call_count  (always 1)
  - duration_ms
  - cost_usd    (if > 0)
  - error_count (only if status == "error")

TimescaleDB's continuous aggregates roll these up hourly and daily for the dashboard.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from amo.models import TraceEvent

if TYPE_CHECKING:
    from ..config import PipelineConfig

logger = logging.getLogger("amo.pipeline")

# (time, org_id, agent_name, metric_name, value, framework)
MetricRow = tuple[Any, str, str, str, float, str]


def _span_to_metrics(event: TraceEvent) -> list[MetricRow]:
    rows: list[MetricRow] = [
        (event.timestamp, event.org_id, event.agent_name, "call_count",  1.0,                 event.framework),
        (event.timestamp, event.org_id, event.agent_name, "duration_ms", float(event.duration_ms), event.framework),
    ]
    if event.cost_usd > 0:
        rows.append(
            (event.timestamp, event.org_id, event.agent_name, "cost_usd", event.cost_usd, event.framework)
        )
    if event.status == "error":
        rows.append(
            (event.timestamp, event.org_id, event.agent_name, "error_count", 1.0, event.framework)
        )
    return rows


_INSERT_SQL = """
    INSERT INTO agent_metrics (time, org_id, agent_name, metric_name, value, framework)
    VALUES (%s, %s, %s, %s, %s, %s)
"""


class TimescaleWriter:
    def __init__(self, config: PipelineConfig) -> None:
        import psycopg2  # type: ignore[import]

        self._conn = psycopg2.connect(config.timescale_dsn)
        self._conn.autocommit = False
        self._batch_size = config.timescale_batch_size
        self._flush_interval_s = config.timescale_flush_interval_s
        self._buffer: list[MetricRow] = []
        self._lock = threading.Lock()

        self._timer = threading.Timer(self._flush_interval_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def write(self, event: TraceEvent) -> None:
        rows = _span_to_metrics(event)
        with self._lock:
            self._buffer.extend(rows)
            if len(self._buffer) >= self._batch_size:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def close(self) -> None:
        self._timer.cancel()
        self.flush()
        self._conn.close()

    def _timer_flush(self) -> None:
        self.flush()
        self._timer = threading.Timer(self._flush_interval_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            cursor = self._conn.cursor()
            cursor.executemany(_INSERT_SQL, batch)
            self._conn.commit()
            logger.debug("AMO TimescaleDB: inserted %d metric rows", len(batch))
        except Exception as exc:
            logger.error("AMO TimescaleDB: insert failed (%d rows): %s", len(batch), exc)
            try:
                self._conn.rollback()
            except Exception:
                pass
            self._buffer[:0] = batch  # re-queue for next flush

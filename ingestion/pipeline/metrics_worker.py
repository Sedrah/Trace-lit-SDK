"""
Metrics worker — reads from trace_lit.spans.normalized, aggregates, writes to TimescaleDB.

Runs as a separate consumer group (tracelit-metrics) so it can lag behind or restart
independently from the ingestion worker. This is intentional: metrics can be
recomputed from normalized events at any time.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig
    from .writers.timescale import TimescaleWriter

logger = logging.getLogger("trace_lit.pipeline")


class MetricsWorker:
    def __init__(self, config: PipelineConfig, ts_writer: TimescaleWriter) -> None:
        self._config = config
        self._ts_writer = ts_writer
        self._stop_event = threading.Event()

    def run(self) -> None:
        from confluent_kafka import Consumer, KafkaError  # type: ignore[import]

        consumer = Consumer(
            {
                "bootstrap.servers": ",".join(self._config.kafka_brokers),
                "group.id": self._config.metrics_group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "session.timeout.ms": 30_000,
            }
        )
        consumer.subscribe([self._config.normalized_topic])
        logger.info("AMO metrics worker started — consuming %s", self._config.normalized_topic)

        try:
            while not self._stop_event.is_set():
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("AMO metrics consumer error: %s", msg.error())
                    continue

                self._process(consumer, msg)
        finally:
            self._ts_writer.flush()
            consumer.close()
            logger.info("AMO metrics worker stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def _process(self, consumer: object, msg: object) -> None:
        import json

        from pydantic import ValidationError

        from trace_lit.models import TraceEvent

        try:
            payload: bytes = msg.value()  # type: ignore[attr-defined]
            raw = json.loads(payload)
            event = TraceEvent.model_validate(raw)
            self._ts_writer.write(event)
            consumer.commit(msg)  # type: ignore[attr-defined]
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("AMO metrics: invalid normalized event — skipping: %s", exc)
            consumer.commit(msg)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("AMO metrics: unhandled error — skipping: %s", exc)
            try:
                consumer.commit(msg)  # type: ignore[attr-defined]
            except Exception:
                pass

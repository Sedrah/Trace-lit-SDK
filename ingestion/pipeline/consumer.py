"""
Ingestion worker — reads from trace_lit.spans.raw, normalizes, writes to ClickHouse,
and produces normalized events to trace_lit.spans.normalized.

Design decisions:
- Manual offset commit: offset is committed ONLY after ClickHouse write succeeds.
  If the writer fails, the message is reprocessed on restart. No spans are silently lost.
- Unprocessable messages (bad schema, persistent write failures) go to the dead letter
  topic (trace_lit.spans.dead) rather than being dropped silently.
- The worker runs on a single thread. To scale throughput, run multiple instances
  in the same consumer group — Kafka distributes partitions automatically.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig
    from .dead_letter import DeadLetterProducer
    from .normalizer import Normalizer
    from .producer import NormalizedProducer
    from .writers.clickhouse import ClickHouseWriter

logger = logging.getLogger("trace_lit.pipeline")


class IngestionWorker:
    def __init__(
        self,
        config: "PipelineConfig",
        normalizer: "Normalizer",
        ch_writer: "ClickHouseWriter",
        producer: "NormalizedProducer",
        dlq: "DeadLetterProducer",
    ) -> None:
        self._config     = config
        self._normalizer = normalizer
        self._ch_writer  = ch_writer
        self._producer   = producer
        self._dlq        = dlq
        self._running    = False
        self._stop_event = threading.Event()

    def run(self) -> None:
        from confluent_kafka import Consumer, KafkaError  # type: ignore[import]

        consumer = Consumer(
            {
                "bootstrap.servers": ",".join(self._config.kafka_brokers),
                "group.id": self._config.ingestion_group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "session.timeout.ms": 30_000,
                "max.poll.interval.ms": 300_000,
            }
        )
        consumer.subscribe([self._config.raw_topic])
        self._running = True
        logger.info("AMO ingestion worker started — consuming %s", self._config.raw_topic)

        try:
            while not self._stop_event.is_set():
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue  # end of partition — not an error
                    logger.error("AMO consumer error: %s", msg.error())
                    continue

                self._process(consumer, msg)
        finally:
            # Flush any buffered ClickHouse rows before exiting
            self._ch_writer.flush()
            consumer.close()
            self._running = False
            logger.info("AMO ingestion worker stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def _process(self, consumer: object, msg: object) -> None:
        try:
            payload: bytes = msg.value()  # type: ignore[attr-defined]
            headers = msg.headers() or []  # type: ignore[attr-defined]

            normalized = self._normalizer.normalize(payload, headers)
            if normalized is None:
                # Deliberately rejected (unknown format, missing required fields).
                # Route to DLQ so the raw bytes are preserved for inspection.
                self._dlq.send(msg, reason="rejected by normalizer — unknown format or missing fields")
                consumer.commit(msg)  # type: ignore[attr-defined]
                return

            # Write to ClickHouse (buffered — flushes automatically on batch_size / interval)
            self._ch_writer.write(normalized)

            # Produce to trace_lit.spans.normalized for downstream consumers (metrics, evals)
            self._producer.produce(normalized)

            # Commit offset only after successful ClickHouse write
            consumer.commit(msg)  # type: ignore[attr-defined]

        except Exception as exc:
            # Route to DLQ so the message isn't silently lost.
            # Commit the offset after routing so we don't reprocess indefinitely.
            self._dlq.send(msg, reason=str(exc))
            try:
                consumer.commit(msg)  # type: ignore[attr-defined]
            except Exception:
                pass

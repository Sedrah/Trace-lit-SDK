"""
DeadLetterProducer — routes unprocessable messages to trace_lit.spans.dead.

Each DLQ message keeps the original raw bytes and carries metadata headers
so the cause is visible without parsing the payload. Messages can be replayed
by re-producing them to trace_lit.spans.raw with the original headers.

Headers added:
  x-error-reason      — why the message was rejected (truncated at 500 chars)
  x-original-topic    — source topic (e.g. trace_lit.spans.raw)
  x-original-partition — Kafka partition number
  x-original-offset   — Kafka offset (aids point-in-time debugging)
  x-failed-at         — ISO 8601 UTC timestamp of the failure
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig

logger = logging.getLogger("trace_lit.pipeline")


class DeadLetterProducer:
    def __init__(self, config: "PipelineConfig") -> None:
        from confluent_kafka import Producer  # type: ignore[import]

        self._topic    = config.dead_letter_topic
        self._producer = Producer(
            {"bootstrap.servers": ",".join(config.kafka_brokers)}
        )

    def send(self, msg: object, reason: str) -> None:
        """
        Route a failed Kafka message to the dead letter topic.
        Never raises — if DLQ produce itself fails, logs at ERROR and moves on.
        """
        try:
            original_headers = list(msg.headers() or [])  # type: ignore[attr-defined]
            dlq_headers = original_headers + [
                ("x-error-reason",       reason[:500].encode()),
                ("x-original-topic",     (msg.topic() or "").encode()),  # type: ignore[attr-defined]
                ("x-original-partition", str(msg.partition()).encode()),  # type: ignore[attr-defined]
                ("x-original-offset",    str(msg.offset()).encode()),     # type: ignore[attr-defined]
                ("x-failed-at",          datetime.now(timezone.utc).isoformat().encode()),
            ]
            self._producer.produce(
                self._topic,
                key=msg.key(),          # type: ignore[attr-defined]
                value=msg.value(),      # type: ignore[attr-defined]
                headers=dlq_headers,
                on_delivery=_log_dlq_delivery,
            )
            self._producer.poll(0)
            logger.warning(
                "AMO DLQ: routed message (topic=%s offset=%s) — reason: %s",
                msg.topic(),            # type: ignore[attr-defined]
                msg.offset(),           # type: ignore[attr-defined]
                reason[:200],
            )
        except Exception as exc:
            logger.error(
                "AMO DLQ: failed to route message to dead letter topic: %s — original reason: %s",
                exc,
                reason[:200],
            )

    def flush(self) -> None:
        self._producer.flush(timeout=5)


def _log_dlq_delivery(err: object, _msg: object) -> None:
    if err:
        logger.error("AMO DLQ: delivery failed: %s", err)

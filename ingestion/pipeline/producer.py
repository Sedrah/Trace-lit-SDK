"""
NormalizedProducer — publishes enriched TraceEvents to amo.spans.normalized.

Downstream consumers (metrics worker, eval engine) read from this topic.
Partitioned by trace_id so all spans of a trace go to the same partition.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig

from amo.models import TraceEvent

logger = logging.getLogger("amo.pipeline")


class NormalizedProducer:
    def __init__(self, config: PipelineConfig) -> None:
        from confluent_kafka import Producer  # type: ignore[import]

        self._topic = config.normalized_topic
        self._producer = Producer(
            {"bootstrap.servers": ",".join(config.kafka_brokers)}
        )

    def produce(self, event: TraceEvent) -> None:
        try:
            self._producer.produce(
                self._topic,
                key=str(event.trace_id).encode(),
                value=event.to_kafka_payload(),
                on_delivery=_log_delivery_error,
            )
            self._producer.poll(0)
        except Exception as exc:
            # Normalizer events not making it to the normalized topic means metrics
            # may be incomplete — log but don't fail the ingestion pipeline.
            logger.warning("AMO producer: failed to produce normalized event: %s", exc)

    def flush(self) -> None:
        self._producer.flush(timeout=5)


def _log_delivery_error(err: object, _msg: object) -> None:
    if err:
        logger.warning("AMO producer: delivery failed: %s", err)

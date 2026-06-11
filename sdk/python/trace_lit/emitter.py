from __future__ import annotations

import logging
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

from .models import TraceEvent

logger = logging.getLogger("trace_lit")

_SENTINEL = object()  # signals the worker thread to shut down


class BaseEmitter(ABC):
    """Base class for all emitter backends."""

    @abstractmethod
    def emit(self, event: TraceEvent) -> None: ...

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_stats(self) -> dict[str, Any]:
        return {"queued": 0, "dropped": 0}


class NoopEmitter(BaseEmitter):
    """Drops all events. Used when TRACELIT_DISABLED=true or backend='noop'."""

    def emit(self, _event: TraceEvent) -> None:
        pass


class ConsoleEmitter(BaseEmitter):
    """Prints events as JSON to stdout. Useful for local development."""

    def emit(self, event: TraceEvent) -> None:
        print(event.model_dump_json(indent=2))


class _BatchingEmitter(BaseEmitter):
    """
    Base for emitters that batch events and publish on a background daemon thread.

    The queue is bounded by max_queue_size. When full, new events are dropped and
    counted — the agent is never blocked. Check get_stats()['dropped'] to detect loss.

    Subclasses implement _publish_batch() to define how batches are delivered.
    """

    def __init__(self, batch_size: int, flush_interval_ms: int, max_queue_size: int = 10_000) -> None:
        self._batch_size       = batch_size
        self._flush_interval_s = flush_interval_ms / 1000.0
        self._drops            = 0
        self._q: queue.Queue[TraceEvent | object] = queue.Queue(maxsize=max_queue_size)
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="amo-emitter"
        )
        self._thread.start()

    def emit(self, event: TraceEvent) -> None:
        try:
            self._q.put_nowait(event)
        except queue.Full:
            self._drops += 1
            # Log on first drop and every 100th to avoid flooding
            if self._drops == 1 or self._drops % 100 == 0:
                logger.warning(
                    "AMO: event queue full — %d spans dropped total. "
                    "Increase max_queue_size or reduce emit rate.",
                    self._drops,
                )

    def get_stats(self) -> dict[str, Any]:
        return {"queued": self._q.qsize(), "dropped": self._drops}

    def flush(self) -> None:
        pass  # subclasses override if the underlying producer has its own flush

    def close(self) -> None:
        """Signal the worker to drain remaining events and stop."""
        self._q.put(_SENTINEL)
        self._thread.join(timeout=10)
        self.flush()

    @abstractmethod
    def _publish_batch(self, batch: list[TraceEvent]) -> None: ...

    def _worker(self) -> None:
        batch: list[TraceEvent] = []
        deadline = time.monotonic() + self._flush_interval_s

        while True:
            timeout = max(0.0, deadline - time.monotonic())
            try:
                item = self._q.get(timeout=timeout)
                if item is _SENTINEL:
                    if batch:
                        self._safe_publish(batch)
                    return
                batch.append(item)  # type: ignore[arg-type]
                if len(batch) >= self._batch_size:
                    self._safe_publish(batch)
                    batch = []
                    deadline = time.monotonic() + self._flush_interval_s
            except Exception:
                # queue.Empty on timeout — flush partial batch and reset deadline
                if batch:
                    self._safe_publish(batch)
                    batch = []
                deadline = time.monotonic() + self._flush_interval_s

    def _safe_publish(self, batch: list[TraceEvent]) -> None:
        """Publish with retry (up to 3 attempts), then drop with a warning."""
        for attempt in range(3):
            try:
                self._publish_batch(batch)
                return
            except Exception as exc:
                if attempt < 2:
                    time.sleep(0.1 * (2**attempt))  # 100ms, 200ms
                else:
                    self._drops += len(batch)
                    logger.warning(
                        "AMO: dropped %d spans after 3 failed publish attempts: %s",
                        len(batch),
                        exc,
                    )


class KafkaEmitter(_BatchingEmitter):
    """
    Publishes batches to Kafka using confluent-kafka.

    The api_key is sent in message headers so the ingestion pipeline can resolve
    api_key → org_id server-side. It never appears in the event payload.
    """

    def __init__(
        self,
        api_key: str,
        brokers: list[str],
        topic: str,
        batch_size: int,
        flush_interval_ms: int,
        max_queue_size: int = 10_000,
    ) -> None:
        try:
            from confluent_kafka import Producer  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "confluent-kafka is required for the Kafka backend. "
                "Install it with: pip install 'Tracelit-SDK[kafka]'"
            ) from exc

        self._topic = topic
        self._api_key_header = [("X-Tracelit-Api-Key", api_key.encode())]
        self._producer = Producer({"bootstrap.servers": ",".join(brokers)})
        super().__init__(
            batch_size=batch_size,
            flush_interval_ms=flush_interval_ms,
            max_queue_size=max_queue_size,
        )

    def flush(self) -> None:
        self._producer.flush(timeout=5)

    def _publish_batch(self, batch: list[TraceEvent]) -> None:
        for event in batch:
            self._producer.produce(
                self._topic,
                key=str(event.trace_id).encode(),
                value=event.to_kafka_payload(),
                headers=self._api_key_header,
                on_delivery=_log_delivery_error,
            )
        self._producer.poll(0)  # trigger delivery callbacks without blocking


def _log_delivery_error(err: object, _msg: object) -> None:
    if err:
        logger.warning("AMO: Kafka delivery failed: %s", err)


# ---------------------------------------------------------------------------
# Module-level emitter singleton
# ---------------------------------------------------------------------------

_emitter: BaseEmitter | None = None
_emitter_lock = threading.Lock()


def get_emitter() -> BaseEmitter:
    global _emitter
    if _emitter is None:
        with _emitter_lock:
            if _emitter is None:
                from .config import get_config
                _emitter = _create_emitter(get_config())
    return _emitter


def reset_emitter(new_emitter: BaseEmitter | None = None) -> None:
    """Replace the singleton emitter. Called by configure() after config changes."""
    global _emitter
    with _emitter_lock:
        if _emitter is not None:
            _emitter.close()
        _emitter = new_emitter  # None → lazily recreated on next get_emitter() call


def _create_emitter(config: object) -> BaseEmitter:
    from .config import Config
    assert isinstance(config, Config)

    if config.disabled or config.backend == "noop":
        return NoopEmitter()
    if config.backend == "console":
        return ConsoleEmitter()
    if config.backend == "kafka":
        return KafkaEmitter(
            api_key=config.api_key,
            brokers=config.kafka_brokers,
            topic=config.kafka_topic,
            batch_size=config.batch_size,
            flush_interval_ms=config.flush_interval_ms,
            max_queue_size=config.max_queue_size,
        )
    raise ValueError(f"Unknown AMO backend: {config.backend!r}")

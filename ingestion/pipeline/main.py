"""
AMO ingestion pipeline entry point.

Starts three workers on separate threads:
  - IngestionWorker:  trace_lit.spans.raw → normalize → ClickHouse + trace_lit.spans.normalized
  - MetricsWorker:    trace_lit.spans.normalized → aggregate → TimescaleDB
  - OTLP/HTTP server: port 4318 — accepts OTel spans directly (no Kafka round-trip)

Usage:
    tracelit-pipeline                # reads all config from env vars
    python -m pipeline.main          # same

Environment variables (see pipeline/config.py for full list):
    TRACELIT_KAFKA_BROKERS=localhost:9092
    TRACELIT_CLICKHOUSE_HOST=localhost
    TRACELIT_TIMESCALE_DSN=postgresql://tracelit:tracelit_pg_password@localhost:5432/trace_lit
    TRACELIT_API_KEYS={"sk-your-key": "org-your-org"}
    TRACELIT_OTLP_HTTP_PORT=4318   # set to 0 to disable
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from .api_keys import ApiKeyResolver
from .config import PipelineConfig
from .consumer import IngestionWorker
from .metrics_worker import MetricsWorker
from .normalizer import Normalizer
from .otel.receiver import build_otlp_app
from .producer import NormalizedProducer
from .writers.clickhouse import ClickHouseWriter
from .writers.timescale import TimescaleWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("trace_lit.pipeline")


def main() -> None:
    config = PipelineConfig.from_env()

    logger.info("AMO ingestion pipeline starting")
    logger.info("  Kafka brokers: %s", config.kafka_brokers)
    logger.info("  ClickHouse:    %s:%s/%s", config.clickhouse_host, config.clickhouse_port, config.clickhouse_database)
    logger.info("  TimescaleDB:   %s", config.timescale_dsn.split("@")[-1])  # hide credentials
    if config.otlp_http_port:
        logger.info("  OTLP/HTTP:     0.0.0.0:%d", config.otlp_http_port)

    # Build services
    resolver = ApiKeyResolver.from_json(
        config.api_keys_json,
        timescale_dsn=config.timescale_dsn,
        cache_ttl_s=config.key_cache_ttl_s,
    )
    normalizer = Normalizer(resolver)
    ch_writer = ClickHouseWriter(config)
    ts_writer = TimescaleWriter(config)
    producer = NormalizedProducer(config)

    # Build Kafka workers
    ingestion_worker = IngestionWorker(config, normalizer, ch_writer, producer)
    metrics_worker = MetricsWorker(config, ts_writer)

    stop_event = threading.Event()
    otlp_server = None

    def shutdown(signum: int, _frame: object) -> None:
        logger.info("AMO pipeline: received signal %d — shutting down gracefully", signum)
        ingestion_worker.stop()
        metrics_worker.stop()
        if otlp_server is not None:
            otlp_server.should_exit = True
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    ingestion_thread = threading.Thread(
        target=ingestion_worker.run, name="tracelit-ingestion", daemon=False
    )
    metrics_thread = threading.Thread(
        target=metrics_worker.run, name="tracelit-metrics", daemon=False
    )

    ingestion_thread.start()
    metrics_thread.start()

    # Start OTLP/HTTP server if port is configured
    otlp_thread = None
    if config.otlp_http_port:
        import uvicorn

        otlp_app = build_otlp_app(resolver, ch_writer, producer)
        otlp_cfg = uvicorn.Config(
            otlp_app,
            host="0.0.0.0",
            port=config.otlp_http_port,
            log_level="warning",
            access_log=False,
        )
        otlp_server = uvicorn.Server(otlp_cfg)
        otlp_thread = threading.Thread(
            target=otlp_server.run, name="tracelit-otlp-http", daemon=False
        )
        otlp_thread.start()

    # Block until shutdown signal
    stop_event.wait()

    ingestion_thread.join(timeout=30)
    metrics_thread.join(timeout=30)
    if otlp_thread is not None:
        otlp_thread.join(timeout=10)

    # Final flush
    ch_writer.close()
    ts_writer.close()
    producer.flush()
    resolver.close()

    logger.info("AMO pipeline shutdown complete. Stats: %s", normalizer.stats)
    sys.exit(0)


if __name__ == "__main__":
    main()

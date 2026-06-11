from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PipelineConfig:
    # Kafka
    kafka_brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    raw_topic: str = "trace_lit.spans.raw"
    normalized_topic: str = "trace_lit.spans.normalized"
    dead_letter_topic: str = "trace_lit.spans.dead"
    metrics_topic: str = "trace_lit.metrics"
    ingestion_group_id: str = "tracelit-ingestion"
    metrics_group_id: str = "tracelit-metrics"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "trace_lit"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # TimescaleDB
    timescale_dsn: str = "postgresql://tracelit:tracelit_pg_password@localhost:5432/trace_lit"

    # Batching
    clickhouse_batch_size: int = 500
    clickhouse_flush_interval_s: float = 2.0
    timescale_batch_size: int = 1000
    timescale_flush_interval_s: float = 5.0

    # api_key → org_id map loaded from env (JSON string)
    # Format: '{"sk-key1": "org-acme", "sk-key2": "org-globex"}'
    # Unknown keys are resolved via TimescaleDB with a TTL cache.
    api_keys_json: str = "{}"
    key_cache_ttl_s: float = 300.0

    # OTLP/HTTP receiver port (4318 is the OTLP standard; 0 = disabled)
    otlp_http_port: int = 4318

    @classmethod
    def from_env(cls) -> PipelineConfig:
        return cls(
            kafka_brokers=os.getenv("TRACELIT_KAFKA_BROKERS", "localhost:9092").split(","),
            raw_topic=os.getenv("TRACELIT_RAW_TOPIC", "trace_lit.spans.raw"),
            normalized_topic=os.getenv("TRACELIT_NORMALIZED_TOPIC", "trace_lit.spans.normalized"),
            dead_letter_topic=os.getenv("TRACELIT_DEAD_LETTER_TOPIC", "trace_lit.spans.dead"),
            metrics_topic=os.getenv("TRACELIT_METRICS_TOPIC", "trace_lit.metrics"),
            ingestion_group_id=os.getenv("TRACELIT_INGESTION_GROUP_ID", "tracelit-ingestion"),
            metrics_group_id=os.getenv("TRACELIT_METRICS_GROUP_ID", "tracelit-metrics"),
            clickhouse_host=os.getenv("TRACELIT_CLICKHOUSE_HOST", "localhost"),
            clickhouse_port=int(os.getenv("TRACELIT_CLICKHOUSE_PORT", "8123")),
            clickhouse_database=os.getenv("TRACELIT_CLICKHOUSE_DATABASE", "amo"),
            clickhouse_user=os.getenv("TRACELIT_CLICKHOUSE_USER", "default"),
            clickhouse_password=os.getenv("TRACELIT_CLICKHOUSE_PASSWORD", ""),
            timescale_dsn=os.getenv(
                "TRACELIT_TIMESCALE_DSN", "postgresql://tracelit:tracelit_pg_password@localhost:5432/trace_lit"
            ),
            clickhouse_batch_size=int(os.getenv("TRACELIT_CH_BATCH_SIZE", "500")),
            clickhouse_flush_interval_s=float(os.getenv("TRACELIT_CH_FLUSH_INTERVAL_S", "2.0")),
            timescale_batch_size=int(os.getenv("TRACELIT_TS_BATCH_SIZE", "1000")),
            timescale_flush_interval_s=float(os.getenv("TRACELIT_TS_FLUSH_INTERVAL_S", "5.0")),
            api_keys_json=os.getenv("TRACELIT_API_KEYS", "{}"),
            key_cache_ttl_s=float(os.getenv("TRACELIT_KEY_CACHE_TTL_S", "300")),
            otlp_http_port=int(os.getenv("TRACELIT_OTLP_HTTP_PORT", "4318")),
        )

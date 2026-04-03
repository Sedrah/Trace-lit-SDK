from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PipelineConfig:
    # Kafka
    kafka_brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    raw_topic: str = "amo.spans.raw"
    normalized_topic: str = "amo.spans.normalized"
    metrics_topic: str = "amo.metrics"
    ingestion_group_id: str = "amo-ingestion"
    metrics_group_id: str = "amo-metrics"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "amo"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # TimescaleDB
    timescale_dsn: str = "postgresql://amo:amo@localhost:5432/amo"

    # Batching
    clickhouse_batch_size: int = 500
    clickhouse_flush_interval_s: float = 2.0
    timescale_batch_size: int = 1000
    timescale_flush_interval_s: float = 5.0

    # api_key → org_id map loaded from env (JSON string)
    # Format: '{"sk-key1": "org-acme", "sk-key2": "org-globex"}'
    # In SaaS this is replaced by a DB lookup; for MVP it's env-configured.
    api_keys_json: str = "{}"

    @classmethod
    def from_env(cls) -> PipelineConfig:
        return cls(
            kafka_brokers=os.getenv("AMO_KAFKA_BROKERS", "localhost:9092").split(","),
            raw_topic=os.getenv("AMO_RAW_TOPIC", "amo.spans.raw"),
            normalized_topic=os.getenv("AMO_NORMALIZED_TOPIC", "amo.spans.normalized"),
            metrics_topic=os.getenv("AMO_METRICS_TOPIC", "amo.metrics"),
            ingestion_group_id=os.getenv("AMO_INGESTION_GROUP_ID", "amo-ingestion"),
            metrics_group_id=os.getenv("AMO_METRICS_GROUP_ID", "amo-metrics"),
            clickhouse_host=os.getenv("AMO_CLICKHOUSE_HOST", "localhost"),
            clickhouse_port=int(os.getenv("AMO_CLICKHOUSE_PORT", "8123")),
            clickhouse_database=os.getenv("AMO_CLICKHOUSE_DATABASE", "amo"),
            clickhouse_user=os.getenv("AMO_CLICKHOUSE_USER", "default"),
            clickhouse_password=os.getenv("AMO_CLICKHOUSE_PASSWORD", ""),
            timescale_dsn=os.getenv(
                "AMO_TIMESCALE_DSN", "postgresql://amo:amo@localhost:5432/amo"
            ),
            clickhouse_batch_size=int(os.getenv("AMO_CH_BATCH_SIZE", "500")),
            clickhouse_flush_interval_s=float(os.getenv("AMO_CH_FLUSH_INTERVAL_S", "2.0")),
            timescale_batch_size=int(os.getenv("AMO_TS_BATCH_SIZE", "1000")),
            timescale_flush_interval_s=float(os.getenv("AMO_TS_FLUSH_INTERVAL_S", "5.0")),
            api_keys_json=os.getenv("AMO_API_KEYS", "{}"),
        )

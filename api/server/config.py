from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiConfig:
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "trace_lit"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    timescale_dsn: str = "postgresql://tracelit:tracelit_pg_password@localhost:5432/trace_lit"

    # Optional Kafka brokers — used only for /health/deep Kafka probe
    kafka_brokers: str = ""

    # Auth key cache TTL in seconds
    key_cache_ttl_s: int = 300

    # Default pagination
    default_page_size: int = 50
    max_page_size: int = 500

    @classmethod
    def from_env(cls) -> ApiConfig:
        return cls(
            clickhouse_host=os.getenv("TRACELIT_CLICKHOUSE_HOST", "localhost"),
            clickhouse_port=int(os.getenv("TRACELIT_CLICKHOUSE_PORT", "8123")),
            clickhouse_database=os.getenv("TRACELIT_CLICKHOUSE_DATABASE", "amo"),
            clickhouse_user=os.getenv("TRACELIT_CLICKHOUSE_USER", "default"),
            clickhouse_password=os.getenv("TRACELIT_CLICKHOUSE_PASSWORD", ""),
            timescale_dsn=os.getenv(
                "TRACELIT_TIMESCALE_DSN", "postgresql://tracelit:tracelit_pg_password@localhost:5432/trace_lit"
            ),
            kafka_brokers=os.getenv("TRACELIT_KAFKA_BROKERS", ""),
            key_cache_ttl_s=int(os.getenv("TRACELIT_KEY_CACHE_TTL_S", "300")),
            default_page_size=int(os.getenv("TRACELIT_DEFAULT_PAGE_SIZE", "50")),
            max_page_size=int(os.getenv("TRACELIT_MAX_PAGE_SIZE", "500")),
        )

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiConfig:
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "amo"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    timescale_dsn: str = "postgresql://amo:amo@localhost:5432/amo"

    # Auth key cache TTL in seconds
    key_cache_ttl_s: int = 300

    # Default pagination
    default_page_size: int = 50
    max_page_size: int = 500

    @classmethod
    def from_env(cls) -> ApiConfig:
        return cls(
            clickhouse_host=os.getenv("AMO_CLICKHOUSE_HOST", "localhost"),
            clickhouse_port=int(os.getenv("AMO_CLICKHOUSE_PORT", "8123")),
            clickhouse_database=os.getenv("AMO_CLICKHOUSE_DATABASE", "amo"),
            clickhouse_user=os.getenv("AMO_CLICKHOUSE_USER", "default"),
            clickhouse_password=os.getenv("AMO_CLICKHOUSE_PASSWORD", ""),
            timescale_dsn=os.getenv(
                "AMO_TIMESCALE_DSN", "postgresql://amo:amo@localhost:5432/amo"
            ),
            key_cache_ttl_s=int(os.getenv("AMO_KEY_CACHE_TTL_S", "300")),
            default_page_size=int(os.getenv("AMO_DEFAULT_PAGE_SIZE", "50")),
            max_page_size=int(os.getenv("AMO_MAX_PAGE_SIZE", "500")),
        )

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Config:
    """Immutable SDK configuration. Create a new instance via configure() to change settings."""

    api_key: str = ""
    backend: Literal["kafka", "console", "noop"] = "kafka"
    kafka_brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    kafka_topic: str = "amo.spans.raw"
    batch_size: int = 100
    flush_interval_ms: int = 500
    sampling_rate: float = 1.0
    log_level: str = "WARNING"
    disabled: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.sampling_rate <= 1.0:
            raise ValueError(f"sampling_rate must be between 0.0 and 1.0, got {self.sampling_rate}")
        if self.backend not in ("kafka", "console", "noop"):
            raise ValueError(f"backend must be 'kafka', 'console', or 'noop', got {self.backend!r}")
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
        if self.flush_interval_ms < 1:
            raise ValueError(f"flush_interval_ms must be >= 1, got {self.flush_interval_ms}")

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            api_key=os.getenv("AMO_API_KEY", ""),
            backend=os.getenv("AMO_BACKEND", "kafka"),  # type: ignore[arg-type]
            kafka_brokers=os.getenv("AMO_KAFKA_BROKERS", "localhost:9092").split(","),
            kafka_topic=os.getenv("AMO_KAFKA_TOPIC", "amo.spans.raw"),
            batch_size=int(os.getenv("AMO_BATCH_SIZE", "100")),
            flush_interval_ms=int(os.getenv("AMO_FLUSH_INTERVAL_MS", "500")),
            sampling_rate=float(os.getenv("AMO_SAMPLING_RATE", "1.0")),
            log_level=os.getenv("AMO_LOG_LEVEL", "WARNING"),
            disabled=os.getenv("AMO_DISABLED", "").lower() in ("1", "true", "yes"),
        )


# Module-level singleton — replaced atomically by configure()
_config: Config = Config.from_env()


def get_config() -> Config:
    return _config


def _set_config(config: Config) -> None:
    global _config
    _config = config

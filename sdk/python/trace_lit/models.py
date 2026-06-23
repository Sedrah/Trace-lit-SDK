from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    error_type: str
    message: str
    traceback: str | None = None


class TraceEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Tenant — always "default" in self-host; overwritten by pipeline from api_key header
    org_id: str = "default"

    # Span identity
    trace_id: UUID = Field(default_factory=uuid4)
    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None

    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0

    # Agent context
    framework: Literal["langchain", "langgraph", "crewai", "openclaw", "raw"] = "raw"
    agent_name: str
    action: str

    # Outcome
    status: Literal["success", "error", "timeout"] = "success"
    error: ErrorDetail | None = None

    # LLM usage — populated by framework wrappers, not @trace on plain functions
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # calculated by ingestion pipeline from token counts + model pricing
    model: str | None = None

    # I/O capture — only populated when capture_io=True in SDK config.
    # Transient fields: ingestion may redact before writing to storage.
    input_text: str | None = None
    output_text: str | None = None

    # Prompt versioning — prompt_content is transient: the ingestion pipeline hashes it
    # to detect mutations and never persists it onto the span itself. prompt_hash and
    # prompt_version are populated server-side; the SDK never sets them directly.
    prompt_name: str = ""
    prompt_content: str | None = None
    prompt_hash: str = ""
    prompt_version: int = 0

    # Arbitrary extra data
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_kafka_payload(self) -> bytes:
        """Serialize to UTF-8 JSON bytes for Kafka. api_key is NOT included here — it goes in headers."""
        return self.model_dump_json().encode()

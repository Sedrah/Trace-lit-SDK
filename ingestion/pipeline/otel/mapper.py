"""
Map an OTLP/HTTP JSON ExportTraceServiceRequest payload to TraceEvent objects.

Supports attribute namespaces from:
  - OTel Gen AI semantic conventions  (gen_ai.*)
  - OpenInference / Arize Phoenix      (llm.*, openinference.*)
  - Raw OTel spans                     (service.name → agent_name, span.name → action)

Trace/span IDs arrive as either:
  - 32/16-char hex strings (most OTel exporters, including Python SDK ≥1.20)
  - Base64-encoded bytes   (older exporters; also what protobuf JSON mapping emits)
Both are handled automatically.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from trace_lit.models import ErrorDetail, TraceEvent

logger = logging.getLogger("trace_lit.otel")

# Attribute keys, checked in priority order
_ATTR_MODEL = (
    "gen_ai.request.model",
    "gen_ai.system",
    "llm.model_name",
    "llm.invocation_parameters.model",
)
_ATTR_INPUT_TOKENS = (
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.prompt_tokens",
    "llm.token_count.prompt",
)
_ATTR_OUTPUT_TOKENS = (
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.completion_tokens",
    "llm.token_count.completion",
)

# Map instrumentation scope name prefix → framework literal
_SCOPE_FRAMEWORK: list[tuple[str, str]] = [
    ("openinference.instrumentation.langgraph", "langgraph"),
    ("opentelemetry.instrumentation.langgraph", "langgraph"),
    ("openinference.instrumentation.langchain", "langchain"),
    ("opentelemetry.instrumentation.langchain", "langchain"),
    ("openinference.instrumentation.crewai",    "crewai"),
    ("opentelemetry.instrumentation.crewai",    "crewai"),
]

# OTel status codes
_STATUS_ERROR = 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def map_otlp_json(payload: dict[str, Any], org_id: str) -> list[TraceEvent]:
    """Convert an OTLP ExportTraceServiceRequest dict → list of TraceEvents."""
    events: list[TraceEvent] = []
    for rs in payload.get("resourceSpans", []):
        resource_attrs = _flat_attrs(rs.get("resource", {}).get("attributes", []))
        service_name: str = resource_attrs.get("service.name", "unknown")

        for ss in rs.get("scopeSpans", []):
            scope_name: str = ss.get("scope", {}).get("name", "")
            framework = _scope_to_framework(scope_name)

            for span in ss.get("spans", []):
                try:
                    events.append(_map_span(span, service_name, framework, org_id))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("otel mapper: skipping span — %s", exc)

    return events


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _map_span(
    span: dict[str, Any],
    service_name: str,
    framework: str,
    org_id: str,
) -> TraceEvent:
    attrs = _flat_attrs(span.get("attributes", []))

    trace_id = _decode_trace_id(span["traceId"])
    span_id  = _decode_span_id(span["spanId"])
    parent_raw = span.get("parentSpanId")
    parent_id  = _decode_span_id(parent_raw) if parent_raw else None

    start_ns = int(span.get("startTimeUnixNano", 0))
    end_ns   = int(span.get("endTimeUnixNano", 0))
    timestamp   = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc)
    duration_ms = max(0, (end_ns - start_ns) // 1_000_000)

    # Status — check events for exception first, then span status code
    status = "success"
    error_detail: ErrorDetail | None = None
    for evt in span.get("events", []):
        if evt.get("name") == "exception":
            ea = _flat_attrs(evt.get("attributes", []))
            error_detail = ErrorDetail(
                error_type=ea.get("exception.type", "Exception"),
                message=ea.get("exception.message", ""),
                traceback=ea.get("exception.stacktrace"),
            )
            status = "error"
            break

    if status == "success" and span.get("status", {}).get("code") == _STATUS_ERROR:
        status = "error"

    model         = _pick(attrs, _ATTR_MODEL)
    input_tokens  = int(_pick(attrs, _ATTR_INPUT_TOKENS) or 0)
    output_tokens = int(_pick(attrs, _ATTR_OUTPUT_TOKENS) or 0)
    agent_name    = attrs.get("agent.name") or service_name

    # Strip known LLM/OTel keys from metadata to avoid bloat
    _known = {*_ATTR_MODEL, *_ATTR_INPUT_TOKENS, *_ATTR_OUTPUT_TOKENS, "agent.name"}
    metadata = {k: v for k, v in attrs.items() if k not in _known}

    return TraceEvent(
        org_id=org_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_id,
        timestamp=timestamp,
        duration_ms=duration_ms,
        framework=framework,  # type: ignore[arg-type]
        agent_name=agent_name,
        action=span.get("name", "span"),
        status=status,  # type: ignore[arg-type]
        error=error_detail,
        model=str(model) if model else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        metadata=metadata,
    )


def _flat_attrs(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten [{key, value: {stringValue/intValue/...}}] → {key: value}."""
    result: dict[str, Any] = {}
    for attr in attributes:
        key = attr.get("key", "")
        val = attr.get("value", {})
        for field, cast in (
            ("stringValue", str),
            ("intValue",    int),
            ("doubleValue", float),
            ("boolValue",   bool),
        ):
            if field in val:
                result[key] = cast(val[field])
                break
    return result


def _pick(attrs: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in attrs:
            return attrs[k]
    return None


def _scope_to_framework(scope_name: str) -> str:
    for prefix, fw in _SCOPE_FRAMEWORK:
        if scope_name.startswith(prefix):
            return fw
    return "raw"


def _decode_trace_id(raw: str) -> UUID:
    """Accept 32-char hex or base64-encoded 16 bytes → UUID."""
    if len(raw) == 32:
        return UUID(hex=raw)
    return UUID(bytes=base64.b64decode(_pad(raw)))


def _decode_span_id(raw: str) -> UUID:
    """Accept 16-char hex or base64-encoded 8 bytes → UUID (zero-padded to 16 bytes)."""
    if len(raw) == 16:
        b = bytes.fromhex(raw)
    else:
        b = base64.b64decode(_pad(raw))
    # Pad 8-byte span ID to 16 bytes for UUID compatibility
    return UUID(bytes=b"\x00" * (16 - len(b)) + b)


def _pad(s: str) -> str:
    """Add base64 padding if missing."""
    return s + "=" * (-len(s) % 4)

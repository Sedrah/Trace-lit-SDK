"""
OTLP/HTTP receiver — FastAPI app that accepts OpenTelemetry spans.

Endpoints
---------
POST /v1/traces   OTLP/HTTP JSON   (Content-Type: application/json)
POST /v1/traces   OTLP/HTTP proto  (Content-Type: application/x-protobuf)
GET  /health      liveness probe

Authentication
--------------
  Authorization: Bearer <tracelit-api-key>   (standard OTel / OTLP header)
  X-Tracelit-Api-Key: <key>                  (fallback for legacy clients)

Configuring any OTel SDK to send here:
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer sk-your-key"
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .mapper import map_otlp_json

if TYPE_CHECKING:
    from ..api_keys import ApiKeyResolver
    from ..cost import calculate_cost as _calc_cost_type
    from ..producers import NormalizedProducer
    from ..writers.clickhouse import ClickHouseWriter

logger = logging.getLogger("trace_lit.otel")


def build_otlp_app(
    resolver: "ApiKeyResolver",
    ch_writer: "ClickHouseWriter",
    producer: "NormalizedProducer",
) -> FastAPI:
    from ..cost import calculate_cost

    app = FastAPI(title="Trace-lit OTLP Receiver", docs_url=None, redoc_url=None)

    @app.post("/v1/traces", status_code=200)
    async def receive_traces(request: Request) -> JSONResponse:
        org_id = _resolve_org(request, resolver)
        if org_id is None:
            raise HTTPException(status_code=401, detail="Invalid or missing API key.")

        content_type = request.headers.get("content-type", "")
        body = await request.body()

        if "application/x-protobuf" in content_type:
            payload = _parse_protobuf(body)
        else:
            try:
                payload = json.loads(body)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body.")

        events = map_otlp_json(payload, org_id)
        accepted = 0
        for event in events:
            cost = event.cost_usd
            if cost == 0.0 and (event.input_tokens > 0 or event.output_tokens > 0):
                cost = calculate_cost(event.model, event.input_tokens, event.output_tokens)
                event = event.model_copy(update={"cost_usd": cost})
            ch_writer.write(event)
            producer.produce(event)
            accepted += 1

        logger.debug("otel receiver: accepted %d spans for org=%s", accepted, org_id)
        # OTLP spec requires an empty ExportTraceServiceResponse on success
        return JSONResponse(content={})

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


def _resolve_org(request: Request, resolver: "ApiKeyResolver") -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        key = auth[7:].strip()
        if key:
            return resolver.resolve(key)
    key = request.headers.get("x-tracelit-api-key", "")
    if key:
        return resolver.resolve(key)
    return None


def _parse_protobuf(body: bytes) -> dict:
    """Parse OTLP protobuf → JSON-equivalent dict using opentelemetry-proto."""
    try:
        from google.protobuf.json_format import MessageToDict  # type: ignore[import]
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (  # type: ignore[import]
            ExportTraceServiceRequest,
        )
    except ImportError:
        raise HTTPException(
            status_code=415,
            detail=(
                "Protobuf support requires opentelemetry-proto. "
                "Send Content-Type: application/json or install the dependency."
            ),
        )

    try:
        msg = ExportTraceServiceRequest()
        msg.ParseFromString(body)
        return MessageToDict(msg, preserving_proto_field_name=True, including_default_value_fields=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid protobuf body: {exc}")

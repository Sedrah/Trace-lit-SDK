"""
GET /health       — shallow liveness probe (no DB calls)
GET /health/deep  — checks ClickHouse, PostgreSQL, and optionally Kafka
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/deep")
async def health_deep(request: Request) -> JSONResponse:
    cfg    = request.app.state.config
    checks: dict[str, dict[str, Any]] = {}

    await asyncio.gather(
        _check_clickhouse(request, checks),
        _check_postgres(request, checks),
        _check_kafka(cfg, checks),
    )

    degraded = any(c["status"] != "ok" for c in checks.values())
    overall  = "degraded" if degraded else "ok"

    return JSONResponse(
        status_code=200 if not degraded else 503,
        content={"status": overall, "checks": checks},
    )


async def _check_clickhouse(request: Request, out: dict) -> None:
    t = time.monotonic()
    try:
        loop   = asyncio.get_running_loop()
        client = request.app.state.ch_client
        await loop.run_in_executor(None, lambda: client.query("SELECT 1"))
        out["clickhouse"] = {"status": "ok", "latency_ms": _ms(t)}
    except Exception as exc:
        out["clickhouse"] = {"status": "down", "latency_ms": _ms(t), "error": str(exc)}


async def _check_postgres(request: Request, out: dict) -> None:
    t = time.monotonic()
    try:
        pool = request.app.state.pg_pool
        await pool.fetchval("SELECT 1")
        out["postgres"] = {"status": "ok", "latency_ms": _ms(t)}
    except Exception as exc:
        out["postgres"] = {"status": "down", "latency_ms": _ms(t), "error": str(exc)}


async def _check_kafka(cfg: Any, out: dict) -> None:
    if not cfg.kafka_brokers:
        return  # Kafka probe is optional — skip if not configured

    t = time.monotonic()
    try:
        from confluent_kafka.admin import AdminClient  # type: ignore[import]
        loop   = asyncio.get_running_loop()
        client = AdminClient({"bootstrap.servers": cfg.kafka_brokers, "socket.timeout.ms": 3000})
        meta   = await loop.run_in_executor(None, lambda: client.list_topics(timeout=3))
        out["kafka"] = {"status": "ok", "latency_ms": _ms(t), "topics": len(meta.topics)}
    except Exception as exc:
        out["kafka"] = {"status": "down", "latency_ms": _ms(t), "error": str(exc)}


def _ms(since: float) -> int:
    return int((time.monotonic() - since) * 1000)

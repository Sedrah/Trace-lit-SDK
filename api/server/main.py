"""
AMO REST API — FastAPI application.

Startup:
    amo-api                    # reads config from env vars
    uvicorn server.main:app    # direct uvicorn invocation

Connections are created once at startup and shared across all requests via
app.state. This keeps each request handler thin and stateless.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import clickhouse_connect
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import ApiConfig
from .routes import admin, agents, alerts, auth, costs, datasets, failures, health, prompts, settings, traces

logger = logging.getLogger("trace_lit.api")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config: ApiConfig | None = None) -> FastAPI:
    cfg = config or ApiConfig.from_env()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("AMO API starting up")
        _app.state.ch_client = clickhouse_connect.get_client(
            host=cfg.clickhouse_host,
            port=cfg.clickhouse_port,
            database=cfg.clickhouse_database,
            username=cfg.clickhouse_user,
            password=cfg.clickhouse_password,
        )
        _app.state.pg_pool = await asyncpg.create_pool(
            cfg.timescale_dsn, min_size=2, max_size=10
        )
        logger.info("AMO API ready")
        yield
        await _app.state.pg_pool.close()
        logger.info("AMO API shutdown complete")

    app = FastAPI(
        title="AMO — Agent Monitoring & Observability",
        version="0.1.0",
        description="REST API for traces, costs, failures, agents, and alerts.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.state.config = cfg

    # CORS — allow the dashboard origin in dev; lock down in prod via env
    origins = os.getenv("TRACELIT_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Global error handler — never expose stack traces to callers
    # ---------------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("AMO API unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "An unexpected error occurred.", "detail": None},
        )

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    prefix = "/api/v1"
    app.include_router(health.router)           # /health and /health/deep (no prefix)
    app.include_router(auth.router,     prefix=prefix)
    app.include_router(traces.router,   prefix=prefix)
    app.include_router(agents.router,   prefix=prefix)
    app.include_router(costs.router,    prefix=prefix)
    app.include_router(failures.router, prefix=prefix)
    app.include_router(alerts.router,   prefix=prefix)
    app.include_router(settings.router, prefix=prefix)
    app.include_router(admin.router,    prefix=prefix)
    app.include_router(prompts.router,   prefix=prefix)
    app.include_router(datasets.router,  prefix=prefix)

    return app


# Module-level app instance for uvicorn
app = create_app()


def start() -> None:
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(
        "server.main:app",
        host=os.getenv("TRACELIT_API_HOST", "0.0.0.0"),
        port=int(os.getenv("TRACELIT_API_PORT", "8000")),
        reload=os.getenv("TRACELIT_DEV", "").lower() in ("1", "true"),
    )


if __name__ == "__main__":
    start()

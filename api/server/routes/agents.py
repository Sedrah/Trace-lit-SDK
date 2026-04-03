"""GET /agents and GET /agents/{name}/metrics"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ..auth import require_org
from ..db import timescale as ts
from ..models import (
    AgentListResponse,
    AgentMetricsResponse,
    AgentSummary,
    MetricPoint,
    PageMeta,
)

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    org_id: str = Depends(require_org),
    since: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=24)
    ),
    until: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> AgentListResponse:
    offset = (page - 1) * page_size
    rows, total = await ts.list_agents(request, org_id, since, until, page_size, offset)
    return AgentListResponse(
        items=[AgentSummary(**r) for r in rows],
        meta=PageMeta(
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total,
        ),
    )


@router.get("/{agent_name}/metrics", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    agent_name: str,
    request: Request,
    org_id: str = Depends(require_org),
    metric_name: str = Query("cost_usd"),
    granularity: str = Query("hourly"),
    since: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=24)
    ),
    until: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
) -> AgentMetricsResponse:
    if granularity not in ("hourly", "daily"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="granularity must be 'hourly' or 'daily'.")

    valid_metrics = {"cost_usd", "duration_ms", "call_count", "error_count"}
    if metric_name not in valid_metrics:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"metric_name must be one of: {', '.join(sorted(valid_metrics))}.",
        )

    points = await ts.get_agent_metrics(
        request, org_id, agent_name, metric_name, granularity, since, until
    )
    return AgentMetricsResponse(
        agent_name=agent_name,
        metric_name=metric_name,
        granularity=granularity,
        points=[MetricPoint(**p) for p in points],
    )

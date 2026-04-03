"""GET /traces and GET /traces/{trace_id} and GET /traces/{trace_id}/dag"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_org
from ..db import clickhouse as ch
from ..models import (
    DAGEdge,
    DAGNode,
    DAGResponse,
    PageMeta,
    SpanResponse,
    TraceDetailResponse,
    TraceListResponse,
    TraceResponse,
)

router = APIRouter(prefix="/traces", tags=["Traces"])


def _default_since() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _default_until() -> datetime:
    return datetime.now(timezone.utc)


@router.get("", response_model=TraceListResponse)
async def list_traces(
    request: Request,
    org_id: str = Depends(require_org),
    agent_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    since: datetime = Query(default_factory=_default_since),
    until: datetime = Query(default_factory=_default_until),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> TraceListResponse:
    offset = (page - 1) * page_size
    rows, total = await ch.list_traces(
        request, org_id, agent_name, status, framework, since, until, page_size, offset
    )
    return TraceListResponse(
        items=[TraceResponse(**r) for r in rows],
        meta=PageMeta(
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total,
        ),
    )


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: UUID,
    request: Request,
    org_id: str = Depends(require_org),
) -> TraceDetailResponse:
    trace = await ch.get_trace(request, org_id, trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found.")

    spans = await ch.get_spans(request, org_id, trace_id)
    return TraceDetailResponse(
        **trace,
        spans=[SpanResponse(**s) for s in spans],
    )


@router.get("/{trace_id}/dag", response_model=DAGResponse)
async def get_dag(
    trace_id: UUID,
    request: Request,
    org_id: str = Depends(require_org),
) -> DAGResponse:
    spans = await ch.get_spans(request, org_id, trace_id)
    if not spans:
        raise HTTPException(status_code=404, detail="Trace not found.")

    nodes = [
        DAGNode(
            id=str(s["span_id"]),
            label=f"{s['agent_name']} — {s['action']}",
            agent_name=s["agent_name"],
            action=s["action"],
            status=s["status"],
            duration_ms=s["duration_ms"],
            cost_usd=float(s["cost_usd"]),
            framework=s["framework"],
            error_msg=s.get("error_msg") or None,
        )
        for s in spans
    ]

    edges = [
        DAGEdge(
            source=str(s["parent_span_id"]),
            target=str(s["span_id"]),
            duration_ms=s["duration_ms"],
        )
        for s in spans
        if s.get("parent_span_id")
    ]

    return DAGResponse(trace_id=trace_id, nodes=nodes, edges=edges)

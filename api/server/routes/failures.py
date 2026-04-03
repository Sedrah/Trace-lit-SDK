"""GET /failures"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ..auth import require_org
from ..db import clickhouse as ch
from ..failures import classify
from ..models import FailureListResponse, FailureResponse, PageMeta

router = APIRouter(prefix="/failures", tags=["Failures"])


@router.get("", response_model=FailureListResponse)
async def list_failures(
    request: Request,
    org_id: str = Depends(require_org),
    agent_name: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    since: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=24)
    ),
    until: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> FailureListResponse:
    offset = (page - 1) * page_size
    rows, total = await ch.list_failures(
        request, org_id, agent_name, framework, since, until, page_size, offset
    )

    items = []
    for r in rows:
        classification = classify(r.get("error_type"), r.get("error_msg"))
        items.append(
            FailureResponse(
                span_id=r["span_id"],
                trace_id=r["trace_id"],
                timestamp=r["timestamp"],
                agent_name=r["agent_name"],
                action=r["action"],
                framework=r["framework"],
                duration_ms=r["duration_ms"],
                error_type=r.get("error_type") or None,
                classification=classification.category,
                description=classification.description,
            )
        )

    return FailureListResponse(
        items=items,
        meta=PageMeta(
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total,
        ),
    )

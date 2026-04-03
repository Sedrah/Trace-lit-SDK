"""GET /costs"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ..auth import require_org
from ..db import clickhouse as ch
from ..models import CostBreakdownItem, CostResponse

router = APIRouter(prefix="/costs", tags=["Costs"])


@router.get("", response_model=CostResponse)
async def get_costs(
    request: Request,
    org_id: str = Depends(require_org),
    since: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=24)
    ),
    until: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
    agent_name: Optional[str] = Query(None),
) -> CostResponse:
    data = await ch.get_costs(request, org_id, since, until, agent_name)
    return CostResponse(
        total_cost_usd=data["total_cost_usd"],
        period_start=since,
        period_end=until,
        breakdown=[CostBreakdownItem(**item) for item in data["breakdown"]],
    )

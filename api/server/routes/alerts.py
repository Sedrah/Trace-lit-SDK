"""GET /alerts, POST /alerts, DELETE /alerts/{id}"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from ..auth import require_org
from ..db import timescale as ts
from ..models import AlertRuleListResponse, AlertRuleRequest, AlertRuleResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=AlertRuleListResponse)
async def list_alerts(
    request: Request,
    org_id: str = Depends(require_org),
) -> AlertRuleListResponse:
    rows = await ts.list_alert_rules(request, org_id)
    return AlertRuleListResponse(items=[AlertRuleResponse(**r) for r in rows])


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert(
    body: AlertRuleRequest,
    request: Request,
    org_id: str = Depends(require_org),
) -> AlertRuleResponse:
    valid_metrics = {"cost_usd", "error_rate", "duration_ms"}
    if body.metric not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"metric must be one of: {', '.join(sorted(valid_metrics))}.",
        )
    valid_channels = {"slack", "webhook"}
    if body.channel not in valid_channels:
        raise HTTPException(
            status_code=400,
            detail=f"channel must be one of: {', '.join(sorted(valid_channels))}.",
        )

    row = await ts.create_alert_rule(request, org_id, body.model_dump())
    return AlertRuleResponse(**row)


@router.delete("/{rule_id}", status_code=204, response_class=Response)
async def delete_alert(
    rule_id: int,
    request: Request,
    org_id: str = Depends(require_org),
) -> Response:
    deleted = await ts.delete_alert_rule(request, org_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found.")
    return Response(status_code=204)

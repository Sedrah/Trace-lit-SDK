"""GET /prompts, GET /prompts/{name}/versions, GET /prompts/{name}/versions/{version}[/metrics]"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import require_org
from ..db import clickhouse as ch
from ..models import (
    PromptListResponse,
    PromptSummary,
    PromptVersionDetail,
    PromptVersionListResponse,
    PromptVersionMetrics,
    PromptVersionSummary,
)

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    request: Request,
    org_id: str = Depends(require_org),
) -> PromptListResponse:
    rows = await ch.list_prompts(request, org_id)
    return PromptListResponse(items=[PromptSummary(**r) for r in rows])


@router.get("/{prompt_name}/versions", response_model=PromptVersionListResponse)
async def list_prompt_versions(
    prompt_name: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> PromptVersionListResponse:
    rows = await ch.list_prompt_versions(request, org_id, prompt_name)
    if not rows:
        raise HTTPException(status_code=404, detail="Prompt not found.")
    return PromptVersionListResponse(
        prompt_name=prompt_name,
        items=[PromptVersionSummary(**r) for r in rows],
    )


@router.get(
    "/{prompt_name}/versions/{version}", response_model=PromptVersionDetail
)
async def get_prompt_version(
    prompt_name: str,
    version: int,
    request: Request,
    org_id: str = Depends(require_org),
) -> PromptVersionDetail:
    row = await ch.get_prompt_version(request, org_id, prompt_name, version)
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found.")
    return PromptVersionDetail(**row)


@router.get(
    "/{prompt_name}/versions/{version}/metrics", response_model=PromptVersionMetrics
)
async def get_prompt_version_metrics(
    prompt_name: str,
    version: int,
    request: Request,
    org_id: str = Depends(require_org),
) -> PromptVersionMetrics:
    metrics = await ch.get_prompt_version_metrics(request, org_id, prompt_name, version)
    return PromptVersionMetrics(**metrics)

"""
User-facing key management — authenticated by session token.

GET    /settings/keys         — list SDK API keys for the signed-in org
POST   /settings/keys         — create a new SDK key (returns raw key once)
DELETE /settings/keys/{id}    — revoke a key
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import require_org
from ..db import timescale as ts
from ..models import ApiKeyListResponse, ApiKeyResponse

router = APIRouter(prefix="/settings", tags=["Settings"])


class CreateKeyRequest(BaseModel):
    name: str = "SDK key"


class CreateKeyResponse(BaseModel):
    id: int
    org_id: str
    name: str
    api_key: str   # raw key — shown once, never stored


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@router.get("/keys", response_model=ApiKeyListResponse)
async def list_keys(
    request: Request,
    org_id: str = Depends(require_org),
) -> ApiKeyListResponse:
    rows = await ts.list_api_keys(request, org_id)
    return ApiKeyListResponse(items=[ApiKeyResponse(**r) for r in rows])


@router.post("/keys", response_model=CreateKeyResponse, status_code=201)
async def create_key(
    body: CreateKeyRequest,
    request: Request,
    org_id: str = Depends(require_org),
) -> CreateKeyResponse:
    raw_key  = "sk-" + secrets.token_hex(24)
    key_hash = _sha256(raw_key)
    row = await ts.create_api_key(request, {
        "key_hash":   key_hash,
        "org_id":     org_id,
        "name":       body.name,
        "expires_at": None,
    })
    return CreateKeyResponse(
        id=row["id"],
        org_id=row["org_id"],
        name=row["name"],
        api_key=raw_key,
    )


@router.delete("/keys/{key_id}", status_code=204)
async def delete_key(
    key_id: int,
    request: Request,
    org_id: str = Depends(require_org),
) -> None:
    # Verify key belongs to this org before deleting
    rows = await ts.list_api_keys(request, org_id)
    if not any(r["id"] == key_id for r in rows):
        raise HTTPException(status_code=404, detail="Key not found.")
    await ts.delete_api_key(request, key_id)

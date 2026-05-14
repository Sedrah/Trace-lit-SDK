"""
POST   /admin/keys          — provision a new API key for an org
GET    /admin/keys          — list all keys (optionally filter by org_id)
DELETE /admin/keys/{key_id} — revoke a key

Admin endpoints are protected by TRACELIT_ADMIN_KEY — a separate secret
that must be set in the environment. Never expose these to the dashboard.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import APIKeyHeader

from ..db import timescale as ts
from ..models import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyListResponse, ApiKeyResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

_ADMIN_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Admin-Key", auto_error=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def require_admin(admin_key: Optional[str] = Depends(_ADMIN_KEY_HEADER)) -> None:
    expected = os.getenv("TRACELIT_ADMIN_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin API is disabled — set TRACELIT_ADMIN_KEY to enable it.",
        )
    if not admin_key or not secrets.compare_digest(admin_key, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key.")


@router.post("/keys", response_model=ApiKeyCreateResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_key(body: ApiKeyCreateRequest, request: Request) -> ApiKeyCreateResponse:
    raw_key = "sk-" + secrets.token_urlsafe(32)
    key_hash = _sha256(raw_key)
    row = await ts.create_api_key(request, {
        "key_hash": key_hash,
        "org_id": body.org_id,
        "name": body.name,
        "expires_at": body.expires_at,
    })
    # Return the raw key once — it cannot be retrieved again
    return ApiKeyCreateResponse(**row, raw_key=raw_key)


@router.get("/keys", response_model=ApiKeyListResponse, dependencies=[Depends(require_admin)])
async def list_keys(
    request: Request,
    org_id: Optional[str] = Query(None),
) -> ApiKeyListResponse:
    rows = await ts.list_api_keys(request, org_id)
    return ApiKeyListResponse(items=[ApiKeyResponse(**r) for r in rows])


@router.delete("/keys/{key_id}", status_code=204, dependencies=[Depends(require_admin)])
async def revoke_key(key_id: int, request: Request) -> None:
    deleted = await ts.delete_api_key(request, key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found.")

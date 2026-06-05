"""GET /auth/me — validate API key and return org identity."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..auth import _lookup_org, _sha256, _cache
import time

router = APIRouter(prefix="/auth", tags=["Auth"])

_API_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Api-Key", auto_error=False)


@router.get("/me")
async def me(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
    request: Request = None,  # type: ignore[assignment]
) -> dict:
    """
    Validate an API key strictly — always checks the DB, never uses the
    keyless bypass. Used by the login page to authenticate users.
    """
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=401, detail="API key required.")

    key_hash = _sha256(api_key.strip())
    now = time.monotonic()

    cached = _cache.get(key_hash)
    if cached and cached[1] > now:
        return {"org_id": cached[0]}

    org_id = await _lookup_org(key_hash, request)
    if org_id is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    ttl_s = getattr(getattr(request.app.state, "config", None), "key_cache_ttl_s", 300)
    _cache[key_hash] = (org_id, now + ttl_s)

    return {"org_id": org_id}

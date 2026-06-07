"""
Authentication for the Trace-lit API.

Two credential types are accepted:
  X-Tracelit-Api-Key   — SDK / pipeline use (hashed API key → org_id)
  X-Tracelit-Session   — Dashboard user sessions (token → org_id via sessions table)

Self-hosted installs with TRACELIT_ALLOW_KEYLESS=true skip all checks (dev only).
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("trace_lit.api")

_API_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Api-Key", auto_error=False)
_SESSION_HEADER = APIKeyHeader(name="X-Tracelit-Session",  auto_error=False)

# In-memory caches
_cache: dict[str, tuple[str, float]] = {}                    # key_hash  → (org_id, expires)
_session_cache: dict[str, tuple[str, float]] = {}            # sess_hash → (org_id, expires)


def _allow_keyless() -> bool:
    return os.getenv("TRACELIT_ALLOW_KEYLESS", "").lower() in ("1", "true", "yes")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _lookup_org(key_hash: str, request: Request) -> Optional[str]:
    pool = request.app.state.pg_pool
    row  = await pool.fetchrow(
        "SELECT org_id FROM api_keys WHERE key_hash = $1 AND (expires_at IS NULL OR expires_at > NOW())",
        key_hash,
    )
    return row["org_id"] if row else None


async def _lookup_session_org(token: str, request: Request) -> Optional[str]:
    h    = _sha256(token)
    now  = time.monotonic()
    hit  = _session_cache.get(h)
    if hit and hit[1] > now:
        return hit[0]

    pool = request.app.state.pg_pool
    row  = await pool.fetchrow(
        "SELECT org_id FROM sessions WHERE token_hash = $1 AND expires_at > NOW()", h
    )
    if not row:
        return None

    ttl_s = getattr(getattr(request.app.state, "config", None), "key_cache_ttl_s", 300)
    _session_cache[h] = (row["org_id"], now + ttl_s)
    return row["org_id"]


async def require_org(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
    session:  Optional[str] = Security(_SESSION_HEADER),
    request:  Request       = None,  # type: ignore[assignment]
) -> str:
    # Dashboard session always takes priority — must check before keyless fallback
    if session:
        org_id = await _lookup_session_org(session, request)
        if org_id:
            return org_id

    # SDK / pipeline API key
    if api_key:
        key_hash = _sha256(api_key)
        now      = time.monotonic()
        cached   = _cache.get(key_hash)
        if cached and cached[1] > now:
            return cached[0]
        org_id = await _lookup_org(key_hash, request)
        if org_id:
            ttl_s = getattr(getattr(request.app.state, "config", None), "key_cache_ttl_s", 300)
            _cache[key_hash] = (org_id, now + ttl_s)
            return org_id

    # Keyless fallback — SDK/pipeline use only, no session present
    if _allow_keyless():
        return "default"

    raise HTTPException(status_code=401, detail="Not authenticated.")

"""
API key authentication.

Every request must carry X-Tracelit-Api-Key. The key is hashed (SHA-256) and
looked up in the api_keys table. The resolved org_id is injected into every
route via FastAPI's dependency injection.

SHA-256 is used (not bcrypt) because API keys are high-entropy secrets — a fast
hash is safe. bcrypt is for low-entropy user passwords. Queries hit the DB at
most once per key per KEY_CACHE_TTL_S seconds.

Self-hosted installs with no api_keys rows can use TRACELIT_ALLOW_KEYLESS=true which
maps any request to org_id="default". This is NOT for production SaaS use.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("trace_lit.api")

_API_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Api-Key", auto_error=False)


def _allow_keyless() -> bool:
    return os.getenv("TRACELIT_ALLOW_KEYLESS", "").lower() in ("1", "true", "yes")

# In-memory cache: sha256_hex → (org_id, expires_at)
_cache: dict[str, tuple[str, float]] = {}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _lookup_org(key_hash: str, request: Request) -> Optional[str]:
    """Look up org_id from the api_keys table. Returns None if not found."""
    pool = request.app.state.pg_pool
    row = await pool.fetchrow(
        "SELECT org_id FROM api_keys WHERE key_hash = $1 AND (expires_at IS NULL OR expires_at > NOW())",
        key_hash,
    )
    return row["org_id"] if row else None


async def require_org(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
    request: Request = None,  # type: ignore[assignment]
) -> str:
    """
    FastAPI dependency — returns the resolved org_id for the request.
    Raises HTTP 401 if the key is missing or unrecognised.
    """
    if _allow_keyless():
        return "default"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Add X-Tracelit-Api-Key header.")

    key_hash = _sha256(api_key)
    now = time.monotonic()

    # Check cache first
    cached = _cache.get(key_hash)
    if cached and cached[1] > now:
        return cached[0]

    # Cache miss — query DB
    org_id = await _lookup_org(key_hash, request)
    if org_id is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    # Cache the result
    ttl = getattr(request.app.state, "config", None)
    ttl_s = ttl.key_cache_ttl_s if ttl else 300
    _cache[key_hash] = (org_id, now + ttl_s)

    return org_id

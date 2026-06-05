"""
Auth routes:
  POST /auth/signup        — register with email, sends verification link
  GET  /auth/verify        — consume token, issue API key
  GET  /auth/me            — validate key, return org_id (strict — no keyless bypass)
"""
from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from ..auth import _cache, _lookup_org, _sha256
from ..email import send_verification_email

logger = logging.getLogger("trace_lit.api")
router = APIRouter(prefix="/auth", tags=["Auth"])

_API_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Api-Key", auto_error=False)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COMMON_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: str


class SignupResponse(BaseModel):
    message: str


class VerifyResponse(BaseModel):
    org_id: str
    api_key: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    scheme = forwarded_proto or request.url.scheme
    host   = request.headers.get("x-forwarded-host", "") or request.headers.get("host", "localhost")
    return f"{scheme}://{host}"


def _org_id_from_email(email: str) -> str:
    """Derive a short, readable org slug from an email address."""
    local, domain = email.lower().split("@", 1)
    # Use domain for business emails, local part for common providers
    if domain in _COMMON_DOMAINS:
        base = re.sub(r"[^a-z0-9]+", "-", local).strip("-")
    else:
        base = re.sub(r"[^a-z0-9]+", "-", domain.split(".")[0]).strip("-")
    return base or "org"


def _sha256_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=SignupResponse, status_code=202)
async def signup(body: SignupRequest, request: Request) -> SignupResponse:
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address.")

    pool = request.app.state.pg_pool

    # Check if this email already has a verified key
    existing = await pool.fetchrow(
        "SELECT id FROM api_keys WHERE email = $1 LIMIT 1", email
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Use your API key to sign in.",
        )

    org_id = _org_id_from_email(email)
    token  = secrets.token_urlsafe(32)

    # Upsert pending signup (replace if re-requesting)
    await pool.execute(
        """
        INSERT INTO pending_signups (email, org_id, token, expires_at)
        VALUES ($1, $2, $3, NOW() + INTERVAL '24 hours')
        ON CONFLICT (email) DO UPDATE
            SET token      = EXCLUDED.token,
                org_id     = EXCLUDED.org_id,
                expires_at = EXCLUDED.expires_at
        """,
        email, org_id, token,
    )

    verify_url = f"{_base_url(request)}/verify?token={token}"
    send_verification_email(email, verify_url)

    return SignupResponse(message="Check your email for a verification link.")


@router.get("/verify", response_model=VerifyResponse)
async def verify(token: str, request: Request) -> VerifyResponse:
    if not token:
        raise HTTPException(status_code=400, detail="Missing token.")

    pool = request.app.state.pg_pool

    row = await pool.fetchrow(
        "SELECT email, org_id, expires_at FROM pending_signups WHERE token = $1",
        token,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or already used verification link.")

    from datetime import datetime, timezone
    if datetime.now(timezone.utc) > row["expires_at"].replace(tzinfo=timezone.utc):
        await pool.execute("DELETE FROM pending_signups WHERE token = $1", token)
        raise HTTPException(status_code=410, detail="Verification link has expired. Please sign up again.")

    # Generate API key
    raw_key   = "sk-" + secrets.token_hex(24)
    key_hash  = _sha256_key(raw_key)
    org_id    = row["org_id"]
    email     = row["email"]

    # Make org_id unique if taken
    suffix = 2
    base_org = org_id
    while await pool.fetchrow("SELECT id FROM api_keys WHERE org_id = $1 LIMIT 1", org_id):
        org_id = f"{base_org}-{suffix}"
        suffix += 1

    await pool.execute(
        """
        INSERT INTO api_keys (key_hash, org_id, name, email)
        VALUES ($1, $2, $3, $4)
        """,
        key_hash, org_id, email, email,
    )

    await pool.execute("DELETE FROM pending_signups WHERE token = $1", token)

    logger.info("New org verified: %s (email: %s)", org_id, email)
    return VerifyResponse(org_id=org_id, api_key=raw_key)


@router.get("/me")
async def me(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
    request: Request = None,  # type: ignore[assignment]
) -> dict:
    """Strict key validation — never uses the keyless bypass."""
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=401, detail="API key required.")

    key_hash = _sha256(api_key.strip())
    now      = time.monotonic()

    cached = _cache.get(key_hash)
    if cached and cached[1] > now:
        return {"org_id": cached[0]}

    org_id = await _lookup_org(key_hash, request)
    if org_id is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    ttl_s = getattr(getattr(request.app.state, "config", None), "key_cache_ttl_s", 300)
    _cache[key_hash] = (org_id, now + ttl_s)
    return {"org_id": org_id}

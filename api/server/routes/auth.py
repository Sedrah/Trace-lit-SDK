"""
Magic-link auth — no passwords, no API keys visible to dashboard users.

Flow:
  POST /auth/magic {email}   — create/find user, send magic link
  GET  /auth/verify?token=   — consume token, create 30-day session
  POST /auth/logout          — delete session
  GET  /auth/me              — return {org_id, email} for current session

SDK users authenticate with X-Tracelit-Api-Key as before.
Dashboard users authenticate with X-Tracelit-Session (set by /auth/verify).
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from ..auth import _cache, _lookup_org, _sha256
from ..email import send_verification_email

logger = logging.getLogger("trace_lit.api")
router = APIRouter(prefix="/auth", tags=["Auth"])

_SESSION_HEADER = APIKeyHeader(name="X-Tracelit-Session", auto_error=False)
_API_KEY_HEADER = APIKeyHeader(name="X-Tracelit-Api-Key", auto_error=False)

_EMAIL_RE    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COMMON      = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class MagicRequest(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _org_from_email(email: str) -> str:
    local, domain = email.lower().split("@", 1)
    base = local if domain in _COMMON else domain.split(".")[0]
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "org"


def _base_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host   = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost")
    return f"{scheme}://{host}"


# ---------------------------------------------------------------------------
# Session cache (avoids DB hit on every dashboard request)
# ---------------------------------------------------------------------------

_session_cache: dict[str, tuple[str, str, float]] = {}  # hash → (org_id, email, expires)


async def _lookup_session(token: str, pool) -> Optional[tuple[str, str]]:
    """Return (org_id, email) for a valid session token, or None."""
    h   = _hash(token)
    now = time.monotonic()

    cached = _session_cache.get(h)
    if cached and cached[2] > now:
        return cached[0], cached[1]

    row = await pool.fetchrow(
        """
        SELECT s.org_id, u.email
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = $1 AND s.expires_at > NOW()
        """,
        h,
    )
    if not row:
        return None

    _session_cache[h] = (row["org_id"], row["email"], now + 300)
    return row["org_id"], row["email"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/magic", status_code=202)
async def magic(body: MagicRequest, request: Request) -> dict:
    """Send a magic sign-in link. Creates an account automatically on first use."""
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address.")

    pool  = request.app.state.pg_pool
    token = secrets.token_urlsafe(32)

    # Upsert magic link (re-request cancels previous)
    await pool.execute(
        """
        INSERT INTO magic_links (email, token, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '15 minutes')
        ON CONFLICT DO NOTHING
        """,
        email, token,
    )
    # If conflict (shouldn't happen with unique token), just generate a new one
    existing = await pool.fetchval(
        "SELECT token FROM magic_links WHERE email = $1 AND used_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1",
        email,
    )
    if existing:
        token = existing
    else:
        await pool.execute(
            "INSERT INTO magic_links (email, token) VALUES ($1, $2)",
            email, token,
        )

    verify_url = f"{_base_url(request)}/verify?token={token}"
    send_verification_email(email, verify_url)

    return {"message": "Check your email for a sign-in link."}


@router.get("/verify")
async def verify(token: str, request: Request) -> dict:
    """Consume a magic link token, create/find user, return a 30-day session."""
    if not token:
        raise HTTPException(status_code=400, detail="Missing token.")

    pool = request.app.state.pg_pool

    row = await pool.fetchrow(
        "SELECT email, used_at, expires_at FROM magic_links WHERE token = $1",
        token,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")
    if row["used_at"]:
        raise HTTPException(status_code=410, detail="This link has already been used. Request a new one.")

    if datetime.now(timezone.utc) > row["expires_at"].replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=410, detail="Link expired. Request a new one.")

    email = row["email"]

    # Mark link as used
    await pool.execute("UPDATE magic_links SET used_at = NOW() WHERE token = $1", token)

    # Find or create user
    user = await pool.fetchrow("SELECT id, org_id FROM users WHERE email = $1", email)
    if not user:
        org_id  = _org_from_email(email)
        # Ensure org_id is unique
        suffix  = 2
        base    = org_id
        while await pool.fetchval("SELECT id FROM users WHERE org_id = $1", org_id):
            org_id = f"{base}-{suffix}"
            suffix += 1

        user_id = await pool.fetchval(
            "INSERT INTO users (email, org_id) VALUES ($1, $2) RETURNING id",
            email, org_id,
        )
        # Auto-generate an API key for SDK use (stored hashed, not returned here)
        raw_key  = "sk-" + secrets.token_hex(24)
        key_hash = _hash(raw_key)
        await pool.execute(
            "INSERT INTO api_keys (key_hash, org_id, name) VALUES ($1, $2, $3)",
            key_hash, org_id, "default",
        )
        logger.info("New user created: %s (org: %s)", email, org_id)
    else:
        user_id = user["id"]
        org_id  = user["org_id"]

    # Create session
    session_token = secrets.token_urlsafe(32)
    token_hash    = _hash(session_token)
    await pool.execute(
        "INSERT INTO sessions (user_id, org_id, token_hash, expires_at) VALUES ($1, $2, $3, NOW() + INTERVAL '90 days')",
        user_id, org_id, token_hash,
    )

    return {"session_token": session_token, "org_id": org_id, "email": email}


@router.post("/logout", status_code=204)
async def logout(
    session_token: Optional[str] = Security(_SESSION_HEADER),
    request: Request = None,  # type: ignore[assignment]
) -> None:
    if not session_token:
        return
    pool = request.app.state.pg_pool
    h    = _hash(session_token)
    await pool.execute("DELETE FROM sessions WHERE token_hash = $1", h)
    _session_cache.pop(h, None)


@router.get("/me")
async def me(
    session_token: Optional[str] = Security(_SESSION_HEADER),
    api_key: Optional[str] = Security(_API_KEY_HEADER),
    request: Request = None,  # type: ignore[assignment]
) -> dict:
    """Return org/email for the current session. Strictly validated."""
    pool = request.app.state.pg_pool

    if session_token:
        result = await _lookup_session(session_token, pool)
        if result:
            return {"org_id": result[0], "email": result[1]}

    if api_key:
        key_hash = _sha256(api_key)
        now      = time.monotonic()
        cached   = _cache.get(key_hash)
        if cached and cached[1] > now:
            return {"org_id": cached[0]}
        org_id = await _lookup_org(key_hash, request)
        if org_id:
            ttl_s = getattr(getattr(request.app.state, "config", None), "key_cache_ttl_s", 300)
            _cache[key_hash] = (org_id, now + ttl_s)
            return {"org_id": org_id}

    raise HTTPException(status_code=401, detail="Not authenticated.")

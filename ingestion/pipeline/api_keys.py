"""
api_key → org_id resolver.

Two-tier lookup:
  1. Env-var map (TRACELIT_API_KEYS JSON) — always checked first. Self-hosted
     installs that configure keys via env never touch the DB.
  2. TimescaleDB api_keys table — queried for unknown keys, results cached with
     a short TTL so new keys provisioned via the admin API work without restart.

The empty-string key always maps to "default" (keyless self-host mode).

TRACELIT_API_KEYS format:
    '{"sk-abc123": "org-acme", "sk-def456": "org-globex"}'
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("trace_lit.pipeline")

_NEGATIVE_SENTINEL = object()  # cached "key not found in DB"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class ApiKeyResolver:
    def __init__(
        self,
        key_map: dict[str, str],
        timescale_dsn: Optional[str] = None,
        cache_ttl_s: float = 300.0,
    ) -> None:
        self._map = key_map
        self._dsn = timescale_dsn
        self._ttl = cache_ttl_s
        # cache maps key_hash → (org_id | _NEGATIVE_SENTINEL, expires_at)
        self._cache: dict[str, tuple[object, float]] = {}
        self._lock = threading.Lock()
        self._conn: object = None  # psycopg2 connection, lazy

    @classmethod
    def from_json(cls, json_str: str, timescale_dsn: Optional[str] = None, cache_ttl_s: float = 300.0) -> ApiKeyResolver:
        """Build from a JSON string (TRACELIT_API_KEYS) and optional DB DSN."""
        key_map: dict[str, str] = {"": "default"}  # keyless → default org
        if json_str.strip():
            try:
                loaded = json.loads(json_str)
                key_map.update(loaded)
            except json.JSONDecodeError as exc:
                logger.warning("AMO: failed to parse TRACELIT_API_KEYS: %s", exc)
        return cls(key_map, timescale_dsn=timescale_dsn, cache_ttl_s=cache_ttl_s)

    def resolve(self, api_key: str) -> Optional[str]:
        """Return org_id for api_key, or None if unrecognised/expired."""
        # 1. Env-var map — fast path, no locking needed (read-only after init)
        if api_key in self._map:
            return self._map[api_key]

        if not self._dsn:
            return None

        # 2. DB lookup with TTL cache
        key_hash = _sha256(api_key)
        with self._lock:
            cached = self._cache.get(key_hash)
            if cached is not None:
                value, expires_at = cached
                if time.monotonic() < expires_at:
                    return None if value is _NEGATIVE_SENTINEL else str(value)
                # expired — fall through to re-query

            org_id = self._db_lookup(key_hash)
            self._cache[key_hash] = (
                _NEGATIVE_SENTINEL if org_id is None else org_id,
                time.monotonic() + self._ttl,
            )
            return org_id

    def _db_lookup(self, key_hash: str) -> Optional[str]:
        """Query TimescaleDB for the org_id matching key_hash. Returns None if not found or expired."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT org_id FROM api_keys
                    WHERE key_hash = %s
                      AND (expires_at IS NULL OR expires_at > NOW())
                    LIMIT 1
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as exc:
            logger.error("AMO: api_key DB lookup failed: %s", exc)
            self._conn = None  # force reconnect next time
            return None

    def _get_conn(self) -> object:
        """Return an open psycopg2 connection, reconnecting if needed."""
        import psycopg2  # type: ignore[import]

        if self._conn is None:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = True  # read-only queries, no transaction overhead
        else:
            # Cheap liveness check — reconnect if the connection was dropped
            try:
                self._conn.cursor().execute("SELECT 1")
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = True
        return self._conn

    def add(self, api_key: str, org_id: str) -> None:
        """Register an api_key at runtime (useful in tests)."""
        self._map[api_key] = org_id

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __len__(self) -> int:
        return len(self._map)

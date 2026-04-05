"""
api_key → org_id resolver.

MVP implementation: in-memory dict loaded from TRACELIT_API_KEYS env var (JSON string).

SaaS upgrade path: swap _lookup() for a database query with a short-lived TTL cache.
The interface stays the same — the rest of the pipeline never needs to change.

TRACELIT_API_KEYS format:
    '{"sk-abc123": "org-acme", "sk-def456": "org-globex"}'

The default org "default" is returned for the empty string key, which handles
self-hosted installs that run without an api_key.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger("trace_lit.pipeline")


class ApiKeyResolver:
    def __init__(self, key_map: dict[str, str]) -> None:
        """
        Args:
            key_map: Maps api_key → org_id. Include {"": "default"} for keyless self-host.
        """
        self._map = key_map

    @classmethod
    def from_json(cls, json_str: str) -> ApiKeyResolver:
        """Build from a JSON string (e.g. from env var TRACELIT_API_KEYS)."""
        key_map: dict[str, str] = {"": "default"}  # keyless → default org
        if json_str.strip():
            try:
                loaded = json.loads(json_str)
                key_map.update(loaded)
            except json.JSONDecodeError as exc:
                logger.warning("AMO: failed to parse TRACELIT_API_KEYS: %s", exc)
        return cls(key_map)

    def resolve(self, api_key: str) -> Optional[str]:
        """
        Return the org_id for a given api_key, or None if unrecognised.

        None means the event should be rejected — unknown tenant.
        """
        return self._map.get(api_key)

    def add(self, api_key: str, org_id: str) -> None:
        """Register an api_key at runtime (useful in tests)."""
        self._map[api_key] = org_id

    def __len__(self) -> int:
        return len(self._map)

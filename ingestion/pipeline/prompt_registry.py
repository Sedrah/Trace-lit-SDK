"""
PromptRegistry — content-addressed prompt version tracking.

When a span carries prompt content, the registry hashes it and checks whether
this exact content has been seen before for (org_id, prompt_name). New content
gets the next sequential version number; unchanged content reuses its existing
version, so no duplicate registry rows are ever created.

An in-memory cache avoids a ClickHouse round-trip for every span — only the
first span for any new (org_id, name, hash) combination pays the lookup cost.

Known limitation: if multiple ingestion worker instances process the same new
prompt mutation concurrently, both could compute the same "next version" and
insert duplicate rows. Acceptable for the current single-instance deployment;
revisit (e.g. via a unique constraint table or distributed lock) before scaling
to multiple ingestion replicas.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig

logger = logging.getLogger("trace_lit.pipeline")


class PromptRegistry:
    def __init__(self, config: "PipelineConfig") -> None:
        import clickhouse_connect  # type: ignore[import]

        self._client = clickhouse_connect.get_client(
            host=config.clickhouse_host,
            port=config.clickhouse_port,
            database=config.clickhouse_database,
            username=config.clickhouse_user,
            password=config.clickhouse_password,
        )
        self._cache: dict[tuple[str, str, str], int] = {}  # (org_id, name, hash) -> version
        self._lock = threading.Lock()

    def resolve(self, org_id: str, name: str, content: str) -> tuple[str, int]:
        """Return (hash, version) for this prompt content, registering a new version if unseen."""
        prompt_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        cache_key = (org_id, name, prompt_hash)

        with self._lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return prompt_hash, cached

        version = self._lookup_or_register(org_id, name, prompt_hash, content)

        with self._lock:
            self._cache[cache_key] = version
        return prompt_hash, version

    def _lookup_or_register(self, org_id: str, name: str, prompt_hash: str, content: str) -> int:
        existing = self._client.query(
            "SELECT version FROM prompt_versions "
            "WHERE org_id = {org_id:String} AND prompt_name = {name:String} AND prompt_hash = {hash:String} "
            "LIMIT 1",
            parameters={"org_id": org_id, "name": name, "hash": prompt_hash},
        )
        if existing.result_rows:
            return int(existing.result_rows[0][0])

        max_version_result = self._client.query(
            "SELECT max(version) FROM prompt_versions "
            "WHERE org_id = {org_id:String} AND prompt_name = {name:String}",
            parameters={"org_id": org_id, "name": name},
        )
        current_max = max_version_result.result_rows[0][0] or 0
        version = current_max + 1

        self._client.insert(
            "prompt_versions",
            [[org_id, name, prompt_hash, version, content, datetime.now(timezone.utc)]],
            column_names=["org_id", "prompt_name", "prompt_hash", "version", "content", "first_seen_at"],
        )
        logger.info(
            "AMO prompt registry: new version detected — org=%s name=%s version=%d hash=%s",
            org_id, name, version, prompt_hash,
        )
        return version

    def close(self) -> None:
        pass

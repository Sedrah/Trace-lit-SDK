"""
ClickHouse query layer.

All queries are org_id-scoped — no data crosses tenant boundaries.
Queries return plain dicts; route handlers convert to response models.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger("trace_lit.api")


def _client(request: Any) -> Any:
    return request.app.state.ch_client


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

async def list_traces(
    request: Any,
    org_id: str,
    agent_name: Optional[str],
    status: Optional[str],
    framework: Optional[str],
    since: datetime,
    until: datetime,
    limit: int,
    offset: int,
    prompt_name: Optional[str] = None,
    prompt_version: Optional[int] = None,
) -> tuple[list[dict[str, Any]], int]:
    ch = _client(request)

    # Filter on raw spans; post-aggregation filters (status) go in HAVING.
    span_filters = [
        "org_id = %(org_id)s",
        "timestamp >= %(since)s",
        "timestamp <= %(until)s",
    ]
    params: dict[str, Any] = {"org_id": org_id, "since": since, "until": until}

    if agent_name:
        span_filters.append("agent_name = %(agent_name)s")
        params["agent_name"] = agent_name
    if framework:
        span_filters.append("framework = %(framework)s")
        params["framework"] = framework
    if prompt_name:
        span_filters.append("prompt_name = %(prompt_name)s")
        params["prompt_name"] = prompt_name
    if prompt_version is not None:
        span_filters.append("prompt_version = %(prompt_version)s")
        params["prompt_version"] = prompt_version

    where = " AND ".join(span_filters)

    # status filter: 'error' trace = any span with status='error'
    # We add it as a span-level pre-filter when status='error', or exclude
    # traces with any error span when status='success'. This avoids HAVING
    # with aggregates which ClickHouse 24.x rejects in subquery counts.
    if status == "error":
        span_filters.append("status = 'error'")   # only include error spans, trace_ids that have them
    elif status == "success":
        # exclude trace_ids that have any error span
        span_filters.append(
            "trace_id NOT IN (SELECT trace_id FROM trace_lit.spans "
            "WHERE org_id = %(org_id)s AND status = 'error')"
        )

    where = " AND ".join(span_filters)

    # uniq(trace_id) counts distinct traces directly — no subquery, no nested aggregates
    count_result = ch.query(
        f"SELECT uniq(trace_id) FROM trace_lit.spans WHERE {where}", parameters=params
    )
    total = count_result.first_row[0] if count_result.result_rows else 0

    result = ch.query(
        f"""
        SELECT
            org_id,
            trace_id,
            any(agent_name)               AS agent_name,
            any(framework)                AS framework,
            min(timestamp)                AS started_at,
            max(timestamp)                AS finished_at,
            count()                       AS total_spans,
            countIf(status = 'error')     AS error_spans,
            sum(cost_usd)                 AS total_cost_usd,
            sum(duration_ms)              AS total_duration_ms
        FROM trace_lit.spans
        WHERE {where}
        GROUP BY org_id, trace_id
        ORDER BY started_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        parameters={**params, "limit": limit, "offset": offset},
    )
    rows = []
    for row in result.result_rows:
        d = dict(zip(result.column_names, row))
        # Derive status in Python — avoids ClickHouse 24.x ILLEGAL_AGGREGATION
        # when using aggregate results inside expressions in SELECT.
        d["status"] = "error" if d["error_spans"] > 0 else "success"
        rows.append(d)
    return rows, total


async def get_trace(
    request: Any, org_id: str, trace_id: UUID
) -> Optional[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT
            org_id,
            trace_id,
            any(agent_name)           AS agent_name,
            any(framework)            AS framework,
            min(timestamp)            AS started_at,
            max(timestamp)            AS finished_at,
            count()                   AS total_spans,
            countIf(status = 'error') AS error_spans,
            sum(cost_usd)             AS total_cost_usd,
            sum(duration_ms)          AS total_duration_ms
        FROM trace_lit.spans
        WHERE org_id = %(org_id)s AND trace_id = %(trace_id)s
        GROUP BY org_id, trace_id
        LIMIT 1
        """,
        parameters={"org_id": org_id, "trace_id": str(trace_id)},
    )
    if not result.result_rows:
        return None
    d = dict(zip(result.column_names, result.result_rows[0]))
    d["status"] = "error" if d["error_spans"] > 0 else "success"
    return d


async def get_spans(
    request: Any, org_id: str, trace_id: UUID
) -> list[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT span_id, parent_span_id, timestamp, duration_ms,
               agent_name, action, status, framework, model,
               input_tokens, output_tokens, cost_usd,
               error_type, error_msg, metadata,
               input_text, output_text
        FROM trace_lit.spans
        WHERE org_id = %(org_id)s AND trace_id = %(trace_id)s
        ORDER BY timestamp ASC
        """,
        parameters={"org_id": org_id, "trace_id": str(trace_id)},
    )
    rows = []
    for row in result.result_rows:
        d = dict(zip(result.column_names, row))
        # Parse metadata JSON blob
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = {}
        rows.append(d)
    return rows


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------

async def list_failures(
    request: Any,
    org_id: str,
    agent_name: Optional[str],
    framework: Optional[str],
    since: datetime,
    until: datetime,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    ch = _client(request)

    filters = [
        "org_id = %(org_id)s",
        "status = 'error'",
        "timestamp >= %(since)s",
        "timestamp <= %(until)s",
    ]
    params: dict[str, Any] = {"org_id": org_id, "since": since, "until": until}

    if agent_name:
        filters.append("agent_name = %(agent_name)s")
        params["agent_name"] = agent_name
    if framework:
        filters.append("framework = %(framework)s")
        params["framework"] = framework

    where = " AND ".join(filters)

    count_result = ch.query(
        f"SELECT count() FROM trace_lit.spans WHERE {where}", parameters=params
    )
    total = count_result.first_row[0] if count_result.result_rows else 0

    result = ch.query(
        f"""
        SELECT span_id, trace_id, timestamp, agent_name, action,
               framework, duration_ms, error_type, error_msg
        FROM trace_lit.spans
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        parameters={**params, "limit": limit, "offset": offset},
    )
    rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
    return rows, total


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------

async def get_costs(
    request: Any,
    org_id: str,
    since: datetime,
    until: datetime,
    agent_name: Optional[str],
) -> dict[str, Any]:
    ch = _client(request)

    filters = [
        "org_id = %(org_id)s",
        "timestamp >= %(since)s",
        "timestamp <= %(until)s",
    ]
    params: dict[str, Any] = {"org_id": org_id, "since": since, "until": until}
    if agent_name:
        filters.append("agent_name = %(agent_name)s")
        params["agent_name"] = agent_name

    where = " AND ".join(filters)

    total_result = ch.query(
        f"SELECT sum(cost_usd) FROM trace_lit.spans WHERE {where}", parameters=params
    )
    total_cost = float(total_result.first_row[0] or 0)

    breakdown_result = ch.query(
        f"""
        SELECT agent_name, framework,
               sum(cost_usd) AS total_cost_usd,
               count() AS call_count
        FROM trace_lit.spans
        WHERE {where}
        GROUP BY agent_name, framework
        ORDER BY total_cost_usd DESC
        """,
        parameters=params,
    )
    breakdown = [
        dict(zip(breakdown_result.column_names, row))
        for row in breakdown_result.result_rows
    ]
    for item in breakdown:
        cc = item["call_count"] or 1
        item["avg_cost_per_call"] = float(item["total_cost_usd"]) / cc

    return {"total_cost_usd": total_cost, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

async def list_prompts(request: Any, org_id: str) -> list[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT
            prompt_name,
            max(version)   AS latest_version,
            uniq(version)  AS version_count,
            max(first_seen_at) AS last_updated_at
        FROM trace_lit.prompt_versions
        WHERE org_id = %(org_id)s
        GROUP BY prompt_name
        ORDER BY last_updated_at DESC
        """,
        parameters={"org_id": org_id},
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


async def list_prompt_versions(
    request: Any, org_id: str, prompt_name: str
) -> list[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT
            version,
            prompt_hash,
            first_seen_at,
            substring(content, 1, 200) AS preview
        FROM trace_lit.prompt_versions
        WHERE org_id = %(org_id)s AND prompt_name = %(prompt_name)s
        ORDER BY version ASC
        """,
        parameters={"org_id": org_id, "prompt_name": prompt_name},
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


async def get_prompt_version(
    request: Any, org_id: str, prompt_name: str, version: int
) -> Optional[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT version, prompt_hash, first_seen_at, content
        FROM trace_lit.prompt_versions
        WHERE org_id = %(org_id)s AND prompt_name = %(prompt_name)s AND version = %(version)s
        LIMIT 1
        """,
        parameters={"org_id": org_id, "prompt_name": prompt_name, "version": version},
    )
    if not result.result_rows:
        return None
    return dict(zip(result.column_names, result.result_rows[0]))


async def get_prompt_version_metrics(
    request: Any, org_id: str, prompt_name: str, version: int
) -> dict[str, Any]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT
            count()                    AS span_count,
            avg(cost_usd)               AS avg_cost_usd,
            avg(duration_ms)            AS avg_duration_ms,
            countIf(status = 'error')   AS error_spans
        FROM trace_lit.spans
        WHERE org_id = %(org_id)s AND prompt_name = %(prompt_name)s AND prompt_version = %(version)s
        """,
        parameters={"org_id": org_id, "prompt_name": prompt_name, "version": version},
    )
    row = dict(zip(result.column_names, result.result_rows[0])) if result.result_rows else {}
    span_count = row.get("span_count") or 0
    error_spans = row.get("error_spans") or 0
    return {
        "span_count": span_count,
        "avg_cost_usd": float(row.get("avg_cost_usd") or 0),
        "avg_duration_ms": float(row.get("avg_duration_ms") or 0),
        "error_rate": (error_spans / span_count) if span_count else 0.0,
    }

"""
ClickHouse query layer.

All queries are org_id-scoped — no data crosses tenant boundaries.
Queries return plain dicts; route handlers convert to response models.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger("amo.api")


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
) -> tuple[list[dict[str, Any]], int]:
    ch = _client(request)

    filters = [
        "org_id = %(org_id)s",
        "started_at >= %(since)s",
        "started_at <= %(until)s",
    ]
    params: dict[str, Any] = {
        "org_id": org_id,
        "since": since,
        "until": until,
    }
    if agent_name:
        filters.append("agent_name = %(agent_name)s")
        params["agent_name"] = agent_name
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    if framework:
        filters.append("framework = %(framework)s")
        params["framework"] = framework

    where = " AND ".join(filters)

    count_result = ch.query(
        f"SELECT count() AS n FROM amo.trace_summary WHERE {where}", parameters=params
    )
    total = count_result.first_row[0] if count_result.result_rows else 0

    result = ch.query(
        f"""
        SELECT org_id, trace_id, agent_name, framework,
               started_at, finished_at, total_spans, error_spans,
               total_cost_usd, total_duration_ms, status
        FROM amo.trace_summary
        WHERE {where}
        ORDER BY started_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        parameters={**params, "limit": limit, "offset": offset},
    )
    rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
    return rows, total


async def get_trace(
    request: Any, org_id: str, trace_id: UUID
) -> Optional[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT org_id, trace_id, agent_name, framework,
               started_at, finished_at, total_spans, error_spans,
               total_cost_usd, total_duration_ms, status
        FROM amo.trace_summary
        WHERE org_id = %(org_id)s AND trace_id = %(trace_id)s
        LIMIT 1
        """,
        parameters={"org_id": org_id, "trace_id": str(trace_id)},
    )
    if not result.result_rows:
        return None
    return dict(zip(result.column_names, result.result_rows[0]))


async def get_spans(
    request: Any, org_id: str, trace_id: UUID
) -> list[dict[str, Any]]:
    ch = _client(request)
    result = ch.query(
        """
        SELECT span_id, parent_span_id, timestamp, duration_ms,
               agent_name, action, status, framework, model,
               input_tokens, output_tokens, cost_usd,
               error_type, error_msg, metadata
        FROM amo.spans
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
        f"SELECT count() FROM amo.spans WHERE {where}", parameters=params
    )
    total = count_result.first_row[0] if count_result.result_rows else 0

    result = ch.query(
        f"""
        SELECT span_id, trace_id, timestamp, agent_name, action,
               framework, duration_ms, error_type, error_msg
        FROM amo.spans
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
        f"SELECT sum(cost_usd) FROM amo.spans WHERE {where}", parameters=params
    )
    total_cost = float(total_result.first_row[0] or 0)

    breakdown_result = ch.query(
        f"""
        SELECT agent_name, framework,
               sum(cost_usd) AS total_cost_usd,
               count() AS call_count
        FROM amo.spans
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

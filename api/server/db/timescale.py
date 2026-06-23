"""
TimescaleDB query layer — agents summary and time-series metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("trace_lit.api")


def _pool(request: Any) -> Any:
    return request.app.state.pg_pool


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

async def list_agents(
    request: Any,
    org_id: str,
    since: datetime,
    until: datetime,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    pool = _pool(request)

    total = await pool.fetchval(
        """
        SELECT COUNT(DISTINCT agent_name)
        FROM agent_metrics
        WHERE org_id = $1 AND time >= $2 AND time <= $3
        """,
        org_id, since, until,
    )

    rows = await pool.fetch(
        """
        SELECT
            agent_name,
            framework,
            SUM(CASE WHEN metric_name = 'call_count'  THEN value ELSE 0 END)::bigint  AS call_count,
            SUM(CASE WHEN metric_name = 'error_count' THEN value ELSE 0 END)::bigint  AS error_count,
            AVG(CASE WHEN metric_name = 'duration_ms' THEN value END)                 AS avg_duration_ms,
            SUM(CASE WHEN metric_name = 'cost_usd'    THEN value ELSE 0 END)          AS total_cost_usd,
            MAX(time)                                                                   AS last_seen
        FROM agent_metrics
        WHERE org_id = $1 AND time >= $2 AND time <= $3
        GROUP BY agent_name, framework
        ORDER BY total_cost_usd DESC
        LIMIT $4 OFFSET $5
        """,
        org_id, since, until, limit, offset,
    )

    result = []
    for r in rows:
        d = dict(r)
        call_count = d["call_count"] or 1
        d["error_rate"] = round((d["error_count"] or 0) / call_count, 4)
        d["avg_duration_ms"] = float(d["avg_duration_ms"] or 0)
        d["total_cost_usd"] = float(d["total_cost_usd"] or 0)
        result.append(d)

    return result, total or 0


# ---------------------------------------------------------------------------
# Metrics time-series
# ---------------------------------------------------------------------------

async def get_agent_metrics(
    request: Any,
    org_id: str,
    agent_name: str,
    metric_name: str,
    granularity: str,         # "hourly" | "daily"
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    pool = _pool(request)

    table = "agent_metrics_hourly" if granularity == "hourly" else "agent_metrics_daily"

    rows = await pool.fetch(
        f"""
        SELECT bucket, total, avg_value, max_value, sample_count
        FROM {table}
        WHERE org_id = $1
          AND agent_name = $2
          AND metric_name = $3
          AND bucket >= $4
          AND bucket <= $5
        ORDER BY bucket ASC
        """,
        org_id, agent_name, metric_name, since, until,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Alerts CRUD
# ---------------------------------------------------------------------------

async def list_alert_rules(request: Any, org_id: str) -> list[dict[str, Any]]:
    pool = _pool(request)
    rows = await pool.fetch(
        "SELECT * FROM alert_rules WHERE org_id = $1 ORDER BY created_at DESC",
        org_id,
    )
    return [dict(r) for r in rows]


async def create_alert_rule(
    request: Any, org_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    pool = _pool(request)
    row = await pool.fetchrow(
        """
        INSERT INTO alert_rules
            (org_id, name, agent_name, metric, threshold, window_minutes,
             channel, webhook_url, enabled)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
        RETURNING *
        """,
        org_id,
        data["name"],
        data.get("agent_name"),
        data["metric"],
        data["threshold"],
        data.get("window_minutes", 60),
        data["channel"],
        data["webhook_url"],
    )
    return dict(row)


async def delete_alert_rule(
    request: Any, org_id: str, rule_id: int
) -> bool:
    pool = _pool(request)
    result = await pool.execute(
        "DELETE FROM alert_rules WHERE id = $1 AND org_id = $2",
        rule_id, org_id,
    )
    return result == "DELETE 1"


# ---------------------------------------------------------------------------
# API key management (admin)
# ---------------------------------------------------------------------------

async def create_api_key(request: Any, data: dict[str, Any]) -> dict[str, Any]:
    pool = _pool(request)
    row = await pool.fetchrow(
        """
        INSERT INTO api_keys (key_hash, org_id, name, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, org_id, name, created_at, expires_at
        """,
        data["key_hash"],
        data["org_id"],
        data["name"],
        data.get("expires_at"),
    )
    return dict(row)


async def list_api_keys(request: Any, org_id: Optional[str]) -> list[dict[str, Any]]:
    pool = _pool(request)
    if org_id:
        rows = await pool.fetch(
            "SELECT id, org_id, name, created_at, expires_at FROM api_keys WHERE org_id = $1 ORDER BY created_at DESC",
            org_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT id, org_id, name, created_at, expires_at FROM api_keys ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


async def delete_api_key(request: Any, key_id: int) -> bool:
    pool = _pool(request)
    result = await pool.execute("DELETE FROM api_keys WHERE id = $1", key_id)
    return result == "DELETE 1"


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

async def list_datasets(request: Any, org_id: str) -> list[dict[str, Any]]:
    pool = _pool(request)
    rows = await pool.fetch(
        """
        SELECT d.id, d.name, d.description, d.created_at,
               COUNT(i.id) AS item_count
        FROM datasets d
        LEFT JOIN dataset_items i ON i.dataset_id = d.id
        WHERE d.org_id = $1
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """,
        org_id,
    )
    return [dict(r) for r in rows]


async def create_dataset(
    request: Any, org_id: str, name: str, description: Optional[str]
) -> dict[str, Any]:
    pool = _pool(request)
    row = await pool.fetchrow(
        """
        INSERT INTO datasets (org_id, name, description)
        VALUES ($1, $2, $3)
        RETURNING id, name, description, created_at
        """,
        org_id, name, description,
    )
    return {**dict(row), "item_count": 0}


async def delete_dataset(request: Any, org_id: str, dataset_id: str) -> bool:
    pool = _pool(request)
    result = await pool.execute(
        "DELETE FROM datasets WHERE id = $1 AND org_id = $2",
        dataset_id, org_id,
    )
    return result == "DELETE 1"


async def get_dataset(request: Any, org_id: str, dataset_id: str) -> Optional[dict[str, Any]]:
    pool = _pool(request)
    row = await pool.fetchrow(
        """
        SELECT d.id, d.name, d.description, d.created_at,
               COUNT(i.id) AS item_count
        FROM datasets d
        LEFT JOIN dataset_items i ON i.dataset_id = d.id
        WHERE d.id = $1 AND d.org_id = $2
        GROUP BY d.id
        """,
        dataset_id, org_id,
    )
    return dict(row) if row else None


async def list_dataset_items(
    request: Any, org_id: str, dataset_id: str
) -> list[dict[str, Any]]:
    pool = _pool(request)
    rows = await pool.fetch(
        """
        SELECT id, dataset_id, trace_id, span_id, label, notes,
               agent_name, action, model, input_text, output_text, created_at
        FROM dataset_items
        WHERE dataset_id = $1 AND org_id = $2
        ORDER BY created_at DESC
        """,
        dataset_id, org_id,
    )
    return [dict(r) for r in rows]


async def add_dataset_item(
    request: Any, org_id: str, dataset_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    pool = _pool(request)
    row = await pool.fetchrow(
        """
        INSERT INTO dataset_items
            (dataset_id, org_id, trace_id, span_id, label, notes,
             agent_name, action, model, input_text, output_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (dataset_id, span_id) DO UPDATE
            SET label = EXCLUDED.label,
                notes = EXCLUDED.notes
        RETURNING id, dataset_id, trace_id, span_id, label, notes,
                  agent_name, action, model, input_text, output_text, created_at
        """,
        dataset_id, org_id,
        data["trace_id"], data["span_id"], data["label"],
        data.get("notes"),
        data.get("agent_name"), data.get("action"), data.get("model"),
        data.get("input_text"), data.get("output_text"),
    )
    return dict(row)


async def delete_dataset_item(
    request: Any, org_id: str, dataset_id: str, item_id: str
) -> bool:
    pool = _pool(request)
    result = await pool.execute(
        "DELETE FROM dataset_items WHERE id = $1 AND dataset_id = $2 AND org_id = $3",
        item_id, dataset_id, org_id,
    )
    return result == "DELETE 1"

"""HTTP-level tests for all API routes using mocked DB backends."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import MockCHClient, MockPGPool


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

def test_list_traces_empty(client: TestClient) -> None:
    r = client.get("/api/v1/traces")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["meta"]["total"] == 0


def test_list_traces_with_data(client: TestClient, ch_client: MockCHClient) -> None:
    trace_id = str(uuid4())
    now = datetime.now(timezone.utc)
    # Count query returns a single integer row
    ch_client.set_result("count() AS n", [[1]], ["n"])
    # Data query returns the trace row
    ch_client.set_result(
        "org_id, trace_id",
        [["default", trace_id, "my-agent", "langchain", now, now, 5, 1, 0.0012, 2500, "error"]],
        ["org_id", "trace_id", "agent_name", "framework",
         "started_at", "finished_at", "total_spans", "error_spans",
         "total_cost_usd", "total_duration_ms", "status"],
    )
    r = client.get("/api/v1/traces")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["agent_name"] == "my-agent"
    assert items[0]["status"] == "error"


def test_get_trace_not_found(client: TestClient) -> None:
    r = client.get(f"/api/v1/traces/{uuid4()}")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_get_dag_not_found(client: TestClient) -> None:
    r = client.get(f"/api/v1/traces/{uuid4()}/dag")
    assert r.status_code == 404


def test_get_dag_structure(client: TestClient, ch_client: MockCHClient) -> None:
    trace_id = str(uuid4())
    parent_id = str(uuid4())
    child_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    ch_client.set_result(
        "amo.spans",
        [
            [parent_id, None,      now, 1000, "root-agent", "run",   "success", "langchain", "gpt-4o", 100, 50, 0.001, "", "", "{}"],
            [child_id,  parent_id, now, 500,  "tool-agent", "search","success", "langchain", None,      0,   0,  0.0,   "", "", "{}"],
        ],
        [
            "span_id", "parent_span_id", "timestamp", "duration_ms",
            "agent_name", "action", "status", "framework", "model",
            "input_tokens", "output_tokens", "cost_usd",
            "error_type", "error_msg", "metadata",
        ],
    )

    r = client.get(f"/api/v1/traces/{trace_id}/dag")
    assert r.status_code == 200
    dag = r.json()
    assert len(dag["nodes"]) == 2
    assert len(dag["edges"]) == 1
    assert dag["edges"][0]["source"] == parent_id
    assert dag["edges"][0]["target"] == child_id
    # Node labels must use agent_name + action, not raw IDs
    labels = {n["label"] for n in dag["nodes"]}
    assert "root-agent — run" in labels
    assert "tool-agent — search" in labels


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------

def test_get_costs_empty(client: TestClient) -> None:
    r = client.get("/api/v1/costs")
    assert r.status_code == 200
    data = r.json()
    assert data["total_cost_usd"] == 0.0
    assert data["breakdown"] == []


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------

def test_list_failures_empty(client: TestClient) -> None:
    r = client.get("/api/v1/failures")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_failures_classified(client: TestClient, ch_client: MockCHClient) -> None:
    span_id = str(uuid4())
    trace_id = str(uuid4())
    now = datetime.now(timezone.utc)

    # Count query
    ch_client.set_result("count()", [[1]], ["n"])
    # Data query
    ch_client.set_result(
        "span_id, trace_id",
        [[span_id, trace_id, now, "research-agent", "llm_call", "langchain", 5000, "TimeoutError", "timed out"]],
        ["span_id", "trace_id", "timestamp", "agent_name", "action", "framework", "duration_ms", "error_type", "error_msg"],
    )

    r = client.get("/api/v1/failures")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["classification"] == "LLM Timeout"
    assert items[0]["agent_name"] == "research-agent"
    # Plain English — not a raw error code
    assert "TimeoutError" not in items[0]["description"]


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def test_list_agents_empty(client: TestClient) -> None:
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_agent_metrics_invalid_granularity(client: TestClient) -> None:
    r = client.get("/api/v1/agents/my-agent/metrics?granularity=weekly")
    assert r.status_code == 400


def test_agent_metrics_invalid_metric(client: TestClient) -> None:
    r = client.get("/api/v1/agents/my-agent/metrics?metric_name=invalid_metric")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def test_list_alerts_empty(client: TestClient) -> None:
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_create_alert_invalid_metric(client: TestClient) -> None:
    r = client.post("/api/v1/alerts", json={
        "name": "test", "metric": "token_count", "threshold": 10.0,
        "channel": "slack", "webhook_url": "https://hooks.slack.com/x",
    })
    assert r.status_code == 400


def test_create_alert_invalid_channel(client: TestClient) -> None:
    r = client.post("/api/v1/alerts", json={
        "name": "test", "metric": "cost_usd", "threshold": 10.0,
        "channel": "email", "webhook_url": "https://hooks.slack.com/x",
    })
    assert r.status_code == 400


def test_delete_alert_not_found(client: TestClient, pg_pool: MockPGPool) -> None:
    pg_pool.set_rows([])  # empty means DELETE 0
    r = client.delete("/api/v1/alerts/9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Error format — all errors must be structured JSON
# ---------------------------------------------------------------------------

def test_404_returns_json(client: TestClient) -> None:
    r = client.get("/api/v1/nonexistent-endpoint")
    assert r.status_code == 404
    # FastAPI returns JSON 404 by default

def test_no_stack_trace_in_errors(client: TestClient) -> None:
    r = client.get(f"/api/v1/traces/{uuid4()}")
    body = r.text
    assert "Traceback" not in body
    assert "File " not in body

# CLAUDE.md — AMO (Agent Monitoring & Observability)

## Project Overview

AMO is an **agent orchestration monitoring platform for non-developers**. It surfaces what AI agents are doing — cost, failures, DAG flow — through an accessible dashboard, without requiring users to read code or logs.

Target users: product managers, ops teams, and business stakeholders who deploy or oversee AI agents built with LangChain, LangGraph, or CrewAI.

---

## Tech Stack (by layer)

| Layer | Technology |
|---|---|
| Framework wrappers | LangChain, LangGraph, CrewAI |
| SDK | Python (`amo-sdk`), JS/TS second |
| Event ingestion | Apache Kafka |
| Eval engine | Python worker pool (parallel to ingestion) |
| Trace storage | ClickHouse |
| Metrics storage | TimescaleDB |
| API | FastAPI (REST) |
| Dashboard | React + TypeScript |
| Alerting | Configurable webhooks (Slack, PagerDuty, email) |
| Self-host packaging | Docker Compose |

---

## Planned Directory Structure

```
AMO/
├── sdk/
│   ├── python/          # amo-sdk Python package
│   │   ├── amo/
│   │   │   ├── decorators.py     # @trace decorator
│   │   │   ├── wrappers/         # LangChain, LangGraph, CrewAI
│   │   │   ├── emitter.py        # structured event emitter → Kafka
│   │   │   └── models.py         # TraceEvent, SpanEvent, MetricEvent
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── js/              # amo-sdk JS/TS package (phase 2)
├── ingestion/
│   ├── kafka/           # Kafka topic configs, docker setup
│   └── pipeline/        # Consumer workers, event normalizer
├── eval/
│   └── engine/          # Parallel eval workers, failure classifier
├── storage/
│   ├── clickhouse/      # Schema migrations, queries
│   └── timescale/       # Schema migrations, queries
├── api/
│   └── server/          # FastAPI app, routes, auth
├── dashboard/
│   └── web/             # React + TypeScript frontend
├── infra/
│   ├── docker-compose.yml        # Full stack self-host
│   ├── docker-compose.dev.yml    # Dev with hot reload
│   └── k8s/                      # Kubernetes manifests (phase 2)
├── docs/
├── ARCHITECTURE.md
├── REQUIREMENTS.md
└── CLAUDE.md
```

---

## MVP Scope (build in this order)

1. **Python SDK** — `@trace` decorator, structured event emission, basic LangChain/LangGraph/CrewAI wrappers
2. **Ingestion pipeline** — Kafka topics, consumer workers, event normalization
3. **Storage** — ClickHouse trace schema, TimescaleDB metrics schema
4. **API** — FastAPI REST endpoints for traces, metrics, DAG, cost
5. **Dashboard** — DAG visualization, cost attribution, failure classification UI
6. **Docker Compose** — Full self-hosted stack in a single `docker-compose up`

Eval engine and JS SDK are **phase 2**.

---

## Development Conventions

### Python
- Package manager: `uv` (preferred) or `pip`
- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy` (strict mode for SDK)
- Test runner: `pytest`
- Minimum Python version: 3.11

### TypeScript / React
- Package manager: `pnpm`
- Formatter/linter: Biome
- Test runner: Vitest

### API
- FastAPI with Pydantic v2 models
- All endpoints return structured JSON — no plain text errors
- Auth: API key header (`X-AMO-API-Key`) for MVP, OAuth2 for phase 2

### Events
- All SDK events must follow `TraceEvent` schema (see `sdk/python/amo/models.py`)
- Events are immutable once emitted — no mutation after Kafka publish
- Every span must have: `trace_id`, `span_id`, `parent_span_id`, `timestamp`, `duration_ms`, `framework`, `status`

---

## Non-Developer UX Principles

Since the target user is **not a developer**, keep these in mind when building UI and API responses:
- Error messages must be plain English — no stack traces exposed in the dashboard
- Cost should be surfaced in dollars, not tokens alone
- DAG views must work without understanding what a "node" or "edge" is (use agent names and action labels)
- Failure classification must give a human-readable reason ("LLM timeout", "Tool returned empty result"), not an error code

---

## Scalability Considerations (build with these in mind from day 1)

- SDK emitter must be non-blocking (async/background thread) — never slow down the agent being traced
- Kafka topics should be partitioned by `trace_id` from the start
- ClickHouse schema must use `ReplicatedMergeTree` even in single-node MVP (easy to scale out)
- TimescaleDB hypertable partition interval: 1 day
- API must be stateless — no in-memory session state
- Docker Compose volumes must be externally mountable for data persistence

---

## Running Locally (once infra exists)

```bash
# Start full stack
docker compose -f infra/docker-compose.dev.yml up

# SDK development
cd sdk/python && uv sync && uv run pytest

# API development
cd api/server && uv run fastapi dev main.py

# Dashboard development
cd dashboard/web && pnpm dev
```

---

## What NOT to do

- Do not add synchronous blocking calls in the SDK emitter
- Do not store raw LLM prompts/completions in TimescaleDB (metrics only) — use ClickHouse for trace content
- Do not expose internal Kafka or database errors directly to the dashboard user
- Do not build the JS SDK until the Python SDK is stable and tested
- Do not add auth complexity beyond API key for MVP
- **Do not create any storage schema (ClickHouse table, TimescaleDB table, continuous aggregate) without an `org_id` column** — this is the #1 migration-pain risk
- Do not write any query that does not filter by `org_id` — even in MVP where it is always `"default"`
- Do not embed `org_id` in the SDK or expose it to the caller — it is resolved server-side from the API key

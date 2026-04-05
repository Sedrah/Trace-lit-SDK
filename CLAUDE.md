# CLAUDE.md — Trace-lit (Agent Monitoring & Observability)

## Project Overview

Trace-lit is an **agent orchestration monitoring platform for non-developers**. It surfaces what AI agents are doing — cost, failures, DAG flow — through an accessible dashboard, without requiring users to read code or logs.

Target users: product managers, ops teams, and business stakeholders who deploy or oversee AI agents built with LangChain, LangGraph, or CrewAI.

---

## Tech Stack (by layer)

| Layer | Technology |
|---|---|
| Framework wrappers | LangChain, LangGraph, CrewAI |
| SDK | Python (`Tracelit-SDK`), JS/TS second |
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
│   ├── python/          # Tracelit-SDK Python package
│   │   ├── amo/
│   │   │   ├── decorators.py     # @trace decorator
│   │   │   ├── wrappers/         # LangChain, LangGraph, CrewAI
│   │   │   ├── emitter.py        # structured event emitter → Kafka
│   │   │   └── models.py         # TraceEvent, SpanEvent, MetricEvent
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── js/              # Tracelit-SDK JS/TS package (phase 2)
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
- Auth: API key header (`X-Tracelit-Api-Key`) for MVP, OAuth2 for phase 2

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

## Running Locally

```bash
# 1. Start infra (Kafka, ClickHouse, TimescaleDB)
docker compose -f infra/docker-compose.dev.yml up -d

# 2. Start API (new terminal, from repo root)
cd api
TRACELIT_ALLOW_KEYLESS=true \
TRACELIT_CLICKHOUSE_HOST=localhost \
TRACELIT_CLICKHOUSE_USER=amo \
TRACELIT_CLICKHOUSE_PASSWORD=tracelit_clickhouse_password \
TRACELIT_TIMESCALE_DSN=postgresql://amo:tracelit_pg_password@localhost:5432/amo \
uvicorn server.main:app --reload --port 8000

# 3. Start ingestion pipeline (new terminal)
cd ingestion
TRACELIT_KAFKA_BROKERS=localhost:9092 \
TRACELIT_CLICKHOUSE_HOST=localhost \
TRACELIT_CLICKHOUSE_USER=amo \
TRACELIT_CLICKHOUSE_PASSWORD=tracelit_clickhouse_password \
TRACELIT_TIMESCALE_DSN=postgresql://amo:tracelit_pg_password@localhost:5432/amo \
TRACELIT_API_KEYS='{"your-key":"default"}' \
python -m pipeline.main

# 4. Start dashboard (new terminal)
cd dashboard/web && npm run dev   # http://localhost:3000

# 5. Emit test data
TRACELIT_API_KEYS='{"dev-key":"default"}' python examples/fake_agent.py
```

### SDK tests (no infra needed)
```bash
cd sdk/python && pip install -e ".[dev]" && pytest -v
```

### Infra quirks (ClickHouse on macOS Docker)
- `infra/clickhouse/config/macros.xml` — defines {shard}/{replica} macros for ReplicatedMergeTree
- `infra/clickhouse/config/keeper.xml` — enables built-in Keeper so replication works without ZooKeeper
- `infra/clickhouse/config/listen.xml` — forces 0.0.0.0 binding (fixes macOS IPv4/IPv6 issue)

---

## Known Constraints

- `crewai` and `langgraph` have a hard pip version conflict — cannot be installed together. Use `[all-langchain]` or `[all-crewai]` extras, never `[all]`.
- `@trace` `model=` parameter exists but token counts must be set manually (or via framework wrappers) — plain Python functions emit 0 tokens and $0.00 cost.
- ClickHouse 24.x rejects aggregate expressions inside other expressions in SELECT. Derive computed fields (e.g. `status`) in Python from raw aggregates (`error_spans`).
- `trace_summary` materialized view was removed due to ClickHouse 24.x ILLEGAL_AGGREGATION errors. The API queries `spans` directly with GROUP BY.
- Minimum Python: 3.9 (not 3.11 as originally planned — macOS system Python constraint).

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

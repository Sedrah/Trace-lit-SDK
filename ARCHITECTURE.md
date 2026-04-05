# Trace-lit — Architecture

## Overview

AMO uses a 5-layer stack designed to be lightweight enough to self-host on a single machine but structured to scale horizontally as trace volume grows.

```
Layer 1 — Framework Wrappers
Layer 2 — SDK (event emission)
Layer 3 — Ingestion + Eval
Layer 4 — Storage
Layer 5 — Presentation
```

---

## Layer 1: Framework Wrappers

**Purpose:** Integrate AMO into existing agent frameworks with zero or minimal refactoring.

### Supported frameworks (MVP)
| Framework | Integration mechanism |
|---|---|
| LangChain | `BaseCallbackHandler` subclass |
| LangGraph | Graph state hooks + node wrappers |
| CrewAI | Agent/Task lifecycle hooks |

### Raw Python
The `@trace` decorator works on any Python function — no framework required.

### Design principles
- Wrappers must not change agent behavior — observation only
- All wrappers normalize to the same `TraceEvent` schema before emitting
- Wrappers capture: input, output, start time, end time, LLM calls made, tokens used, tool calls, errors

---

## Layer 2: SDK (`Tracelit-SDK`)

**Purpose:** Thin, non-blocking event emission layer. Converts raw execution data into structured events and publishes to Kafka.

### Key components

#### `@trace` decorator
```
Function call
    → SpanEvent(start)
    → [function executes]
    → SpanEvent(end, duration, status, output)
    → emit to Kafka (async, background thread)
```

#### Event models (`models.py`)
```
TraceEvent
├── org_id: str            # tenant identifier — "default" in self-host MVP, required for SaaS
├── trace_id: UUID         # unique per agent run
├── span_id: UUID          # unique per function/step
├── parent_span_id: UUID   # null for root span
├── timestamp: datetime
├── framework: str         # "langchain" | "langgraph" | "crewai" | "raw"
├── agent_name: str
├── action: str
├── status: "success" | "error" | "timeout"
├── duration_ms: int
├── input_tokens: int
├── output_tokens: int
├── cost_usd: float
├── model: str
├── error: ErrorEvent | null
└── metadata: dict
```

> **SaaS note:** `org_id` is always present in every event. In self-hosted MVP it defaults to `"default"`. In SaaS it is resolved from the API key at ingestion time. This field must never be omitted — adding it retroactively to billions of rows is a painful migration.

#### Emitter (`emitter.py`)
- Async, non-blocking — runs in a background thread/asyncio task
- Batches events (configurable, default: 100 events or 500ms, whichever first)
- Retries on Kafka unavailability with exponential backoff (max 3 retries, then drops + logs warning)
- Never raises exceptions into the calling agent — fail silently, log locally

#### Configuration
```python
# Minimal
amo.configure(api_key="...", endpoint="http://localhost:9092")

# Full
amo.configure(
    api_key="...",           # resolves to org_id at ingestion — never stored raw
    kafka_brokers=["localhost:9092"],
    batch_size=100,
    flush_interval_ms=500,
    sampling_rate=1.0,       # 0.0–1.0, for high-volume cost control
    log_level="WARNING",
)
```

> **SaaS note:** The API key is the tenant identity mechanism. The ingestion pipeline resolves `api_key → org_id` and stamps all events. The SDK never needs to know its own `org_id` — that mapping lives server-side.

---

## Layer 3: Ingestion + Eval

### Kafka Topics

| Topic | Partition key | Purpose |
|---|---|---|
| `trace_lit.spans.raw` | `trace_id` | Raw span events from SDK |
| `trace_lit.spans.normalized` | `trace_id` | After normalization |
| `trace_lit.metrics` | `agent_name` | Aggregated metrics |
| `amo.evals` | `trace_id` | Eval results |
| `amo.alerts` | `agent_name` | Alert triggers |

Partitioning by `trace_id` ensures all spans of a single trace are processed in order by the same consumer.

> **SaaS note:** `org_id` is carried in every Kafka message payload. Topic names are shared across tenants in MVP and early SaaS. For high-volume SaaS (phase 3+), consider per-tenant topic namespacing (`amo.{org_id}.spans.raw`) or a dedicated Kafka cluster per enterprise customer. The payload-level `org_id` means this migration is additive — consumers already have the field to route on.

### Ingestion pipeline (consumer workers)

```
trace_lit.spans.raw
    → Normalizer worker
        → schema validation
        → cost calculation (tokens × model price)
        → DAG edge extraction (parent_span_id → span_id)
    → trace_lit.spans.normalized
        → ClickHouse writer (batch insert)
        → Metrics aggregator → TimescaleDB writer
        → Eval dispatcher → amo.evals (parallel)
```

### Eval engine (phase 2, parallel to ingestion)

The eval engine consumes `trace_lit.spans.normalized` in parallel and writes to `amo.evals`. It does not block ingestion.

MVP eval checks (built-in):
- **Timeout detection** — duration_ms > configurable threshold
- **Empty output detection** — output is null or empty string
- **Repeated failure** — same span fails 3× in a 5-minute window
- **Cost spike** — cost_usd > 2× rolling 7-day average

Phase 2: LLM-based quality scoring, hallucination detection.

---

## Layer 4: Storage

### ClickHouse — Traces

**Why ClickHouse:** columnar storage, extremely fast aggregations over billions of rows, native support for time-range queries, built-in compression.

#### `spans` table
```sql
CREATE TABLE spans (
    org_id       LowCardinality(String),  -- tenant identifier, always "default" in self-host
    trace_id     UUID,
    span_id      UUID,
    parent_span_id UUID,
    timestamp    DateTime64(3, 'UTC'),
    framework    LowCardinality(String),
    agent_name   LowCardinality(String),
    action       String,
    status       LowCardinality(String),
    duration_ms  UInt32,
    input_tokens UInt32,
    output_tokens UInt32,
    cost_usd     Float32,
    model        LowCardinality(String),
    error_type   LowCardinality(String),
    error_msg    String,
    metadata     String   -- JSON blob
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/spans', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY (org_id, trace_id, timestamp)   -- org_id first: all tenant queries filter on it
TTL timestamp + INTERVAL 90 DAY;
```

**Notes:**
- Use `ReplicatedMergeTree` even in single-node MVP — switching later is painful.
- `org_id` is first in `ORDER BY` — ClickHouse skips irrelevant granules for tenant-scoped queries, keeping multi-tenant performance fast without sharding tenants into separate tables.
- For SaaS with very large tenants, a dedicated shard per tenant is possible without schema changes.

### TimescaleDB — Metrics

**Why TimescaleDB:** PostgreSQL-compatible (familiar tooling), purpose-built for time-series, supports continuous aggregates for pre-computed dashboards.

#### `agent_metrics` hypertable
```sql
CREATE TABLE agent_metrics (
    time         TIMESTAMPTZ NOT NULL,
    org_id       TEXT NOT NULL,          -- tenant identifier, always "default" in self-host
    agent_name   TEXT,
    metric_name  TEXT,    -- "cost_usd", "duration_ms", "error_rate", "call_count"
    value        DOUBLE PRECISION,
    framework    TEXT
);
SELECT create_hypertable('agent_metrics', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON agent_metrics (org_id, time DESC);  -- fast per-tenant time queries
```

#### Continuous aggregates (pre-computed)
```sql
-- 1-hour rollup (for dashboard last-24h view) — must include org_id in GROUP BY
-- 1-day rollup  (for dashboard last-30d view) — must include org_id in GROUP BY
```

> **SaaS note:** All continuous aggregates must `GROUP BY org_id` from the start. Recreating aggregates on a large table is expensive.

---

## Layer 5: Presentation

### REST API (FastAPI)

Base URL: `/api/v1`

| Endpoint | Method | Description |
|---|---|---|
| `/traces` | GET | List traces with filters |
| `/traces/{trace_id}` | GET | Full trace with all spans |
| `/traces/{trace_id}/dag` | GET | DAG structure for visualization |
| `/agents` | GET | List agents with summary stats |
| `/agents/{name}/metrics` | GET | Time-series metrics for an agent |
| `/costs` | GET | Cost breakdown by agent/time |
| `/failures` | GET | Failure list with classification |
| `/alerts` | GET/POST | Alert rules |
| `/health` | GET | Service health |

Auth: `X-Tracelit-Api-Key` header (MVP). Keys managed via `POST /api/v1/keys`.

#### API key design (SaaS-forward)

Even in MVP, API keys are structured to support multi-tenancy:

```
Key storage (TimescaleDB `api_keys` table):
  key_hash   TEXT        -- bcrypt hash, never the raw key
  org_id     TEXT        -- the tenant this key belongs to
  name       TEXT        -- human label ("production", "staging")
  scopes     TEXT[]      -- ["read", "write"] — for future RBAC
  created_at TIMESTAMPTZ
  expires_at TIMESTAMPTZ -- nullable
```

Every authenticated API request resolves `key_hash → org_id` and scopes all queries to that `org_id`. This is the only auth change needed to go from single-tenant to multi-tenant — the query layer already filters by `org_id`.

### Dashboard (React + TypeScript)

**Pages:**
1. **Overview** — total cost, error rate, active agents (last 24h)
2. **Traces** — searchable/filterable list of recent agent runs
3. **Trace detail** — DAG visualization, span timeline, cost breakdown
4. **Agents** — per-agent metrics, trend charts
5. **Failures** — classified failure list, human-readable reasons
6. **Alerts** — configure thresholds, notification channels

**DAG visualization:** uses a graph library (React Flow or D3) to render the span tree as a directed acyclic graph. Nodes labeled with `agent_name + action`, edges labeled with duration and status.

### Alerting

Alert delivery targets (MVP): Slack webhook, email (SMTP), generic HTTP webhook.

Alert rule example:
```json
{
  "name": "High cost spike",
  "condition": "cost_usd > 2x 7-day average",
  "agent": "research-agent",
  "channel": "slack",
  "webhook_url": "https://..."
}
```

---

## Self-Host (Docker Compose)

### Services

| Service | Image | Port |
|---|---|---|
| `kafka` | `confluentinc/cp-kafka` | 9092 |
| `zookeeper` | `confluentinc/cp-zookeeper` | 2181 |
| `clickhouse` | `clickhouse/clickhouse-server` | 8123, 9000 |
| `timescaledb` | `timescale/timescaledb` | 5432 |
| `ingestion` | `amo/ingestion` (local build) | — |
| `api` | `amo/api` (local build) | 8000 |
| `dashboard` | `amo/dashboard` (local build) | 3000 |

Single command to start: `docker compose up -d`

---

## Scalability Path

The MVP runs comfortably on a single machine. The architecture supports horizontal scaling at each layer without code changes:

| Layer | Scale-out mechanism |
|---|---|
| SDK | No state — scale out is not needed |
| Kafka | Add brokers, increase partition count |
| Ingestion workers | Add consumer instances (same consumer group) |
| Eval engine | Independent consumer group — scale independently |
| ClickHouse | Add shards via ReplicatedMergeTree |
| TimescaleDB | Read replicas, then multi-node (Citus) |
| API | Stateless FastAPI — add instances behind a load balancer |
| Dashboard | Static build served by CDN |

**Target throughput:**
- MVP (single node): ~1,000 spans/second
- Phase 2 (3-node Kafka + 2-node ClickHouse): ~50,000 spans/second

### SaaS Scaling Path

| Phase | Trigger | Action |
|---|---|---|
| Self-host MVP | Single tenant, low volume | Docker Compose, single node |
| Early SaaS | < 50 orgs, < 10k spans/s | Kubernetes, shared Kafka + ClickHouse, `org_id` row isolation |
| Growth SaaS | > 50 orgs or enterprise SLA | Per-enterprise Kafka topic namespace; ClickHouse sharding by `org_id` |
| Large SaaS | > 500 orgs or 100k+ spans/s | Dedicated ClickHouse cluster per large tenant; Kafka cluster per region |

The schema and event model support all phases above without any structural migration — only infrastructure topology changes.

---

## Security

- All inter-service communication within Docker network (not exposed externally)
- API key hashed (bcrypt) before storage — never stored in plaintext
- No raw LLM prompt/completion content stored unless explicitly opted in (privacy-by-default)
- ClickHouse and TimescaleDB credentials injected via Docker secrets / environment variables
- HTTPS enforced for all external-facing endpoints in production (Traefik reverse proxy recommended)

---

## Decision Log

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Message broker | Kafka | RabbitMQ, Redis Streams | Throughput, replay capability, ecosystem |
| Trace store | ClickHouse | Elasticsearch, Postgres | Columnar aggregations, cost at scale |
| Metrics store | TimescaleDB | InfluxDB, Prometheus | SQL-native, continuous aggregates, familiar |
| API framework | FastAPI | Django, Flask | Async-native, Pydantic v2, fast |
| Dashboard | React + TypeScript | Vue, Svelte | Ecosystem, React Flow for DAG |
| Self-host format | Docker Compose | Helm only | Non-developer friendly, single command |
| Multi-tenant isolation | `org_id` row-level in shared tables | Separate table/DB per tenant | Operationally simpler; ClickHouse ORDER BY org_id makes it fast; dedicated infra available for large tenants later |
| Tenant identity | API key → org_id (server-side resolution) | JWT with embedded org_id | Keys are simpler for SDK config; org_id never exposed in SDK |

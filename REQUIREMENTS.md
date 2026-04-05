# Trace-lit — Requirements

## Functional Requirements

### FR-1: SDK — `@trace` Decorator

| ID | Requirement | MVP |
|---|---|---|
| FR-1.1 | The `@trace` decorator must capture function name, input arguments, output, start time, end time, and status (success/error) | Yes |
| FR-1.2 | Decorated functions must not experience measurable latency overhead from tracing (< 1ms per span) | Yes |
| FR-1.3 | The decorator must work on sync and async Python functions | Yes |
| FR-1.4 | Spans must be linked to a parent trace via `trace_id` propagation through the call stack | Yes |
| FR-1.5 | The decorator must capture uncaught exceptions as error spans without re-raising | Yes |
| FR-1.6 | Tracing must be configurable to be a no-op (disabled) via environment variable | Yes |

### FR-2: Framework Wrappers

| ID | Requirement | MVP |
|---|---|---|
| FR-2.1 | LangChain wrapper must capture chain/agent invocations, LLM calls, tool calls, and token counts via `BaseCallbackHandler` | Yes |
| FR-2.2 | LangGraph wrapper must capture node executions, state transitions, and edge traversals | Yes |
| FR-2.3 | CrewAI wrapper must capture agent task assignments, tool usage, and final outputs | Yes |
| FR-2.4 | All framework wrappers must normalize to the same `TraceEvent` schema | Yes |
| FR-2.5 | JavaScript SDK wrapping LangChain.js | No (phase 2) |

### FR-3: Event Ingestion

| ID | Requirement | MVP |
|---|---|---|
| FR-3.1 | SDK must publish events to Kafka asynchronously without blocking the calling thread | Yes |
| FR-3.2 | Events must be batched (up to 100 events or 500ms flush interval) before publishing | Yes |
| FR-3.3 | Ingestion pipeline must validate event schema and reject malformed events | Yes |
| FR-3.4 | Pipeline must calculate cost in USD from token counts and model pricing | Yes |
| FR-3.5 | Pipeline must extract DAG edges (parent-child span relationships) during normalization | Yes |
| FR-3.6 | Failed Kafka publishes must retry up to 3 times then drop with a local warning log | Yes |
| FR-3.7 | Every event must carry an `org_id` field; pipeline must resolve `api_key → org_id` and stamp events before writing to storage | Yes |
| FR-3.8 | Events with missing or unresolvable `org_id` must be rejected and logged | Yes |

### FR-4: Storage

| ID | Requirement | MVP |
|---|---|---|
| FR-4.1 | All spans must be persisted to ClickHouse with full fidelity | Yes |
| FR-4.2 | Aggregated metrics (cost, duration, error rate, call count) must be stored in TimescaleDB | Yes |
| FR-4.3 | Traces must be queryable by trace_id, agent_name, time range, status, and framework | Yes |
| FR-4.4 | Data retention: traces retained 90 days by default (configurable) | Yes |
| FR-4.5 | Pre-computed hourly and daily rollups for dashboard performance | Yes |
| FR-4.6 | `org_id` must be a column in every ClickHouse table and TimescaleDB table from the initial schema — no exceptions | Yes |
| FR-4.7 | ClickHouse `ORDER BY` must include `org_id` as the leading key for all tenant-queryable tables | Yes |
| FR-4.8 | All continuous aggregates in TimescaleDB must include `org_id` in GROUP BY | Yes |
| FR-4.9 | No query may return data across `org_id` boundaries (enforced at the API layer) | Yes |

### FR-5: REST API

| ID | Requirement | MVP |
|---|---|---|
| FR-5.1 | API must expose endpoints for: traces, agents, costs, failures, DAG, alerts | Yes |
| FR-5.2 | All endpoints must require API key authentication | Yes |
| FR-5.3 | API must return paginated results for list endpoints (default page size: 50) | Yes |
| FR-5.4 | API must return structured JSON errors — no plain text or stack traces | Yes |
| FR-5.5 | API must support time-range filtering on all list endpoints | Yes |
| FR-5.6 | DAG endpoint must return a node/edge structure suitable for direct rendering | Yes |
| FR-5.7 | Every authenticated request must resolve to an `org_id`; all downstream queries must be scoped to that `org_id` | Yes |
| FR-5.8 | API key storage must include: `key_hash`, `org_id`, `name`, `scopes`, `created_at`, `expires_at` | Yes |
| FR-5.9 | API must support key creation, listing, and revocation endpoints | Yes |

### FR-6: Dashboard

| ID | Requirement | MVP |
|---|---|---|
| FR-6.1 | Dashboard must display total cost, error rate, and active agent count for the last 24 hours on the overview page | Yes |
| FR-6.2 | Trace list must be searchable by agent name, status, and time range | Yes |
| FR-6.3 | Trace detail must show an interactive DAG with nodes labeled by agent name and action | Yes |
| FR-6.4 | Trace detail must show a span timeline (Gantt-style) with duration and cost per span | Yes |
| FR-6.5 | Failure list must show human-readable failure classification (not raw error codes) | Yes |
| FR-6.6 | All dollar amounts must be displayed in USD with 4 decimal places for small values | Yes |
| FR-6.7 | Dashboard must be usable by non-developers without any training | Yes |

### FR-7: Failure Classification

| ID | Requirement | MVP |
|---|---|---|
| FR-7.1 | The system must classify failures into human-readable categories | Yes |
| FR-7.2 | MVP failure categories: LLM Timeout, LLM Error, Tool Call Failed, Tool Returned Empty, Agent Loop Detected, Context Length Exceeded, Unknown Error | Yes |
| FR-7.3 | Each failure must include: timestamp, agent name, action, classification, and a plain-English description | Yes |

### FR-8: Cost Attribution

| ID | Requirement | MVP |
|---|---|---|
| FR-8.1 | Cost must be attributed to each span individually (not just per trace) | Yes |
| FR-8.2 | Total cost must roll up to trace level and agent level | Yes |
| FR-8.3 | Cost calculation must use per-model pricing (input vs output token price) | Yes |
| FR-8.4 | Model pricing must be configurable (not hardcoded) to handle pricing changes | Yes |
| FR-8.5 | Dashboard must show cost trend over time per agent | Yes |

### FR-9: Alerting

| ID | Requirement | MVP |
|---|---|---|
| FR-9.1 | Users must be able to define alert rules based on: cost threshold, error rate threshold, duration threshold | Yes |
| FR-9.2 | Alerts must support delivery to Slack webhook and generic HTTP webhook | Yes |
| FR-9.3 | Email alerting (SMTP) | No (phase 2) |
| FR-9.4 | Alert payloads must be human-readable (plain English summary, not just raw data) | Yes |

### FR-10: Self-Host Packaging

| ID | Requirement | MVP |
|---|---|---|
| FR-10.1 | The full stack must start with a single `docker compose up` command | Yes |
| FR-10.2 | Docker Compose must include all dependencies (Kafka, ClickHouse, TimescaleDB) | Yes |
| FR-10.3 | All persistent data must be stored in named Docker volumes (not container-local) | Yes |
| FR-10.4 | Docker Compose must expose a `.env` file for all configurable parameters | Yes |
| FR-10.5 | Kubernetes manifests | No (phase 2) |

---

## Non-Functional Requirements

### Performance

| ID | Requirement |
|---|---|
| NFR-P1 | SDK span emission must add < 1ms latency to the traced function |
| NFR-P2 | API p95 response time < 200ms for list endpoints (up to 1M stored spans) |
| NFR-P3 | API p95 response time < 100ms for single-trace retrieval |
| NFR-P4 | Dashboard initial load < 3 seconds on a standard broadband connection |
| NFR-P5 | Ingestion pipeline must sustain 1,000 spans/second on a single-node deploy |

### Scalability

| ID | Requirement |
|---|---|
| NFR-S1 | Adding Kafka broker instances must increase ingestion throughput linearly |
| NFR-S2 | Adding ingestion worker instances must increase processing throughput without code changes |
| NFR-S3 | ClickHouse schema must support sharding without migration |
| NFR-S4 | API layer must be stateless (horizontally scalable behind a load balancer) |
| NFR-S5 | Multi-tenant isolation must be achievable via row-level `org_id` filtering in MVP, upgrading to per-tenant shards without schema changes |
| NFR-S6 | The system must support at least 1,000 active orgs on shared infrastructure before requiring per-tenant isolation |

### Reliability

| ID | Requirement |
|---|---|
| NFR-R1 | SDK failures must never propagate to the agent being traced |
| NFR-R2 | Kafka consumer must checkpoint offsets — no span is lost on worker restart |
| NFR-R3 | ClickHouse and TimescaleDB must use persistent volumes |

### Security

| ID | Requirement |
|---|---|
| NFR-SEC1 | API keys must be stored hashed (bcrypt) — never in plaintext |
| NFR-SEC2 | All inter-service traffic must be within a private Docker network |
| NFR-SEC3 | LLM prompt/completion content must not be stored unless explicitly opted in |
| NFR-SEC4 | No secrets in Docker images or version-controlled files |
| NFR-SEC5 | Tenant data must never leak across `org_id` boundaries — enforced at the query layer, not just the API layer |
| NFR-SEC6 | API key scope field must be validated on every request — unused in MVP but enforced as present |

### Usability (non-developer users)

| ID | Requirement |
|---|---|
| NFR-U1 | Every error state in the dashboard must display plain-English explanations |
| NFR-U2 | All cost values must be in USD — tokens may be shown as secondary info |
| NFR-U3 | DAG nodes must use agent/action names, not internal IDs |
| NFR-U4 | The dashboard must not require any local setup — works on the browser |

### Observability (self-monitoring)

| ID | Requirement |
|---|---|
| NFR-O1 | All services must expose a `/health` endpoint |
| NFR-O2 | Ingestion lag (Kafka consumer offset lag) must be visible in the dashboard |
| NFR-O3 | SDK must log dropped events (failed publishes) to a local log file |

---

## MVP Deliverables Checklist

- [ ] `Tracelit-SDK` Python package installable via `pip install Tracelit-SDK`
- [ ] `@trace` decorator working on sync + async Python functions
- [ ] LangChain, LangGraph, CrewAI wrappers
- [ ] Kafka ingestion pipeline (consumer + normalizer)
- [ ] ClickHouse schema + migrations
- [ ] TimescaleDB schema + migrations + continuous aggregates
- [ ] FastAPI REST API with all FR-5 endpoints
- [ ] React dashboard with all FR-6 pages
- [ ] Failure classification (FR-7 categories)
- [ ] Cost attribution (FR-8)
- [ ] Basic alerting — Slack + HTTP webhook (FR-9)
- [ ] Docker Compose with `.env` config (FR-10)
- [ ] SDK README with quickstart guide

---

## Out of Scope for MVP

- JavaScript / TypeScript SDK
- LLM-based eval engine (quality scoring, hallucination detection)
- OAuth2 / SSO authentication
- Kubernetes / Helm packaging
- Email alerting
- Data export (CSV/Parquet)
- Custom dashboards / saved views
- Mobile-responsive dashboard
- Org/user management UI (org creation, user invites, role assignment)
- Billing integration
- Per-tenant Kafka topic namespacing
- Dedicated infrastructure per enterprise tenant

## SaaS Phase Requirements (not MVP — planned)

### FR-S1: Org & User Management
- Org creation, user invitations, and role-based access (admin / member / viewer)
- OAuth2 / SSO (Google, GitHub, SAML)

### FR-S2: Billing
- Usage metering by `org_id` (spans ingested, data retained)
- Billing integration (Stripe or equivalent)
- Per-org usage dashboard (visible to org admin)

### FR-S3: Enterprise Isolation
- Option for dedicated Kafka topic namespace per enterprise org
- Option for dedicated ClickHouse shard per enterprise org
- SLA-based data retention configuration per org

### FR-S4: Kubernetes Packaging
- Helm chart for production SaaS deployment
- Horizontal pod autoscaling for API and ingestion workers

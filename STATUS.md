# Trace-lit — Project Status

Last updated: 2026-04-05

---

## Phase 1 — Complete

All MVP components are built, tested locally, and running end-to-end.

| Component | Status | Location | Notes |
|---|---|---|---|
| Python SDK (`@trace`) | Done | `sdk/python/` | Python 3.9+, non-blocking emitter |
| LangChain wrapper | Done | `sdk/python/amo/wrappers/langchain.py` | Callback handler |
| LangGraph wrapper | Done | `sdk/python/amo/wrappers/langgraph.py` | Graph delegation wrapper |
| CrewAI wrapper | Done | `sdk/python/amo/wrappers/crewai.py` | Usage metrics post-kickoff |
| Kafka ingestion pipeline | Done | `ingestion/` | Manual offset commit, cost calc for 20+ models |
| ClickHouse storage | Done | `storage/clickhouse/`, `infra/init/clickhouse/` | ReplicatedMergeTree + Keeper |
| TimescaleDB storage | Done | `storage/timescale/`, `infra/init/timescale/` | Hypertable + hourly/daily aggregates |
| FastAPI REST API | Done | `api/` | Traces, costs, failures, agents, alerts |
| React dashboard | Done | `dashboard/web/` | DAG view, cost charts, failure classifier |
| Docker Compose (dev) | Done | `infra/docker-compose.dev.yml` | Infra only, services run locally |
| Docker Compose (prod) | Done | `infra/docker-compose.yml` | Full stack single command |

---

## Known Issues / Limitations

| Issue | Workaround | Fix target |
|---|---|---|
| `crewai` + `langgraph` pip conflict | Use `[all-langchain]` or `[all-crewai]`, not `[all]` | Phase 2 |
| `trace_summary` MV removed (CH 24.x ILLEGAL_AGGREGATION) | API queries `spans` with GROUP BY | Phase 2 — replace with proper AggregatingMergeTree |
| Cost is $0 for plain `@trace` functions | Pass `model=` + set token counts via `emit_llm_span()` or use framework wrappers | By design — wrappers handle this automatically |
| Kafka advertises `localhost:9092` | Change `KAFKA_ADVERTISED_LISTENERS` to host IP for remote testers | Configuration, not a bug |
| SDK not on PyPI | Install via `pip install git+https://github.com/Sedrah/AMO.git#subdirectory=sdk/python` | Phase 2 |

---

## Phase 2 — Planned

| Item | Priority | Notes |
|---|---|---|
| Publish `Tracelit-SDK` to PyPI | High | Unblocks easy tester onboarding |
| JS/TS SDK | High | Needed for Node.js agent users |
| Eval engine (quality scoring) | Medium | Parallel worker pool, post-ingestion |
| Kubernetes manifests | Medium | For enterprise self-host |
| OAuth2 / SSO | Medium | Replace API key MVP auth |
| SaaS multi-tenant deploy | Low | `org_id` already in all schemas, infra work only |
| `trace_summary` AggregatingMergeTree | Low | Performance optimisation, not correctness |
| Alert delivery (Slack, PagerDuty) | Low | Rules table exists, webhook logic needed |

---

## Infra Notes (ClickHouse on macOS Docker)

Three config files in `infra/clickhouse/config/` are required on macOS:

- `macros.xml` — defines `{shard}=1` / `{replica}=1` for `ReplicatedMergeTree`
- `keeper.xml` — starts ClickHouse Keeper (replaces ZooKeeper)
- `listen.xml` — forces `0.0.0.0` binding (fixes IPv4/IPv6 macOS Docker bug)

These are already mounted in both compose files. Linux hosts may not need them.

---

## Data Flow

```
SDK @trace → Kafka (topic: trace_lit.spans.raw)
  → ingestion pipeline → ClickHouse (amo.spans table)
                       → TimescaleDB (agent_metrics hypertable)
  → API /api/v1/* → dashboard
```

---

## Testing

```bash
# Unit tests (no infra needed)
cd sdk/python  && pytest -v
cd ingestion   && pytest -v
cd api         && pytest -v

# End-to-end (requires docker compose dev stack running)
TRACELIT_API_KEYS='{"dev-key":"default"}' python examples/fake_agent.py
```

# AMO — Agent Monitoring & Observability

**Visibility into your AI agents — for everyone, not just developers.**

AMO is an open-source monitoring platform for AI agent orchestration. It gives product managers, ops teams, and business stakeholders a clear view of what their AI agents are doing: where they succeed, where they fail, what they cost, and why.

---

## The Problem

AI agents built with LangChain, LangGraph, or CrewAI are black boxes to non-technical stakeholders. When something goes wrong — or costs spiral — there's no accessible way to see what happened without reading logs or debugging code.

AMO solves this with a thin SDK that captures structured traces, and a plain-language dashboard that requires no technical knowledge to read.

---

## Key Features

- **`@trace` decorator** — one line of Python to instrument any agent or function
- **DAG visualization** — see the full execution graph of every agent run
- **Cost attribution** — dollars spent per agent, per run, per model
- **Failure classification** — human-readable failure reasons, not error codes
- **LangChain, LangGraph, CrewAI wrappers** — drop-in integration, zero refactoring
- **Docker self-host** — single `docker compose up` for enterprise-friendly deploys
- **REST API** — integrate AMO data into your own tools and dashboards

---

## Architecture (5-Layer Stack)

```
┌─────────────────────────────────────────────┐
│  Framework Layer                             │
│  LangChain · LangGraph · CrewAI wrappers     │
└───────────────────┬─────────────────────────┘
                    │ structured events
┌───────────────────▼─────────────────────────┐
│  SDK Layer (amo-sdk)                         │
│  @trace decorator · async emitter            │
└───────────────────┬─────────────────────────┘
                    │ Kafka publish
┌───────────────────▼─────────────────────────┐
│  Ingestion Layer                             │
│  Kafka pipeline · normalizer · cost calc     │
└──────────┬──────────────────────────────────┘
           │
    ┌──────▼──────┐     ┌────────────────┐
    │  ClickHouse  │     │  TimescaleDB   │
    │  (traces)    │     │  (metrics)     │
    └──────┬───────┘     └───────┬────────┘
           └──────────┬──────────┘
                      │
┌─────────────────────▼───────────────────────┐
│  Presentation Layer                          │
│  Dashboard · REST API · Alerting             │
└─────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full technical detail.

---

## Quick Start

### 1. Install the SDK

```bash
pip install "git+https://github.com/Sedrah/AMO.git#subdirectory=sdk/python"

# With Kafka support (required for sending to AMO):
pip install "git+https://github.com/Sedrah/AMO.git#subdirectory=sdk/python[kafka]"
```

### 2. Instrument your agent

```python
import amo

amo.configure(
    kafka_brokers=["your-amo-host:9092"],
    api_key="your-api-key",
)

@amo.trace(agent_name="research-agent", framework="langchain", model="gpt-4o")
def my_agent_step(query: str) -> str:
    # your existing agent code — unchanged
    ...
```

### 3. LangChain / LangGraph / CrewAI wrappers

```python
# LangChain — pass as a callback
from amo.wrappers.langchain import AmoCallbackHandler
chain = my_chain.with_config(callbacks=[AmoCallbackHandler()])

# LangGraph — wrap the graph
from amo.wrappers.langgraph import AmoTracedGraph
graph = AmoTracedGraph(my_graph)

# CrewAI — wrap the crew
from amo.wrappers.crewai import AmoCrewWrapper
crew = AmoCrewWrapper(my_crew)
```

### 4. Self-host AMO

```bash
git clone https://github.com/Sedrah/AMO.git
cd AMO
cp .env.example .env        # fill in passwords
docker compose -f infra/docker-compose.yml up -d
```

Open `http://localhost` — the dashboard is ready.

---

## Running Locally (for development)

```bash
# 1. Start infra
docker compose -f infra/docker-compose.dev.yml up -d

# 2. Start API (new terminal)
cd api
AMO_ALLOW_KEYLESS=true \
AMO_CLICKHOUSE_HOST=localhost \
AMO_CLICKHOUSE_USER=amo \
AMO_CLICKHOUSE_PASSWORD=amo_clickhouse_password \
AMO_TIMESCALE_DSN=postgresql://amo:amo_pg_password@localhost:5432/amo \
uvicorn server.main:app --reload --port 8000

# 3. Start ingestion pipeline (new terminal)
cd ingestion
AMO_KAFKA_BROKERS=localhost:9092 \
AMO_CLICKHOUSE_HOST=localhost \
AMO_CLICKHOUSE_USER=amo \
AMO_CLICKHOUSE_PASSWORD=amo_clickhouse_password \
AMO_TIMESCALE_DSN=postgresql://amo:amo_pg_password@localhost:5432/amo \
AMO_API_KEYS='{"dev-key":"default"}' \
python -m pipeline.main

# 4. Start dashboard (new terminal)
cd dashboard/web && npm run dev    # http://localhost:3000

# 5. Send test traces
AMO_API_KEYS='{"dev-key":"default"}' python examples/fake_agent.py
```

---

## Roadmap

### Phase 1 — MVP (complete)
- [x] Python SDK — `@trace` decorator, event models, async emitter
- [x] LangChain, LangGraph, CrewAI wrappers
- [x] Kafka ingestion pipeline — consumer, normalizer, cost calculator
- [x] ClickHouse trace storage + TimescaleDB metrics storage
- [x] FastAPI REST API — traces, costs, failures, agents, alerts
- [x] React dashboard — DAG view, cost charts, failure classification
- [x] Docker Compose self-host packaging

### Phase 2 — In Progress
- [ ] JavaScript / TypeScript SDK
- [ ] Eval engine — automated quality scoring
- [ ] Kubernetes manifests
- [ ] OAuth2 / SSO auth
- [ ] SaaS multi-tenant deploy

---

## Requirements

See [REQUIREMENTS.md](REQUIREMENTS.md) for functional and non-functional requirements.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, conventions, and PR process.

---

## License

MIT

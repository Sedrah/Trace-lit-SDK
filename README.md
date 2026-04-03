# AMO — Agent Monitoring & Observability

**Visibility into your AI agents — for everyone, not just developers.**

AMO is an open-source monitoring platform for AI agent orchestration. It gives product managers, ops teams, and business stakeholders a clear view of what their AI agents are doing: where they succeed, where they fail, what they cost, and why.

---

## The Problem

AI agents built with LangChain, LangGraph, or CrewAI are black boxes to non-technical stakeholders. When something goes wrong — or costs spiral — there's no accessible way to see what happened without reading logs or debugging code.

AMO solves this by wrapping your agents with a thin SDK, capturing structured traces and metrics, and surfacing them through a plain-language dashboard.

---

## Key Features (MVP)

- **`@trace` decorator** — one line of Python to instrument any agent or function
- **DAG visualization** — see the full execution graph of every agent run
- **Cost attribution** — dollars spent per agent, per run, per task
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
│  Kafka pipeline · Eval engine (parallel)     │
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

### Instrument your agent (Python)

```python
from amo import trace

@trace
def my_agent(input: str) -> str:
    # your existing agent code — unchanged
    ...
```

### LangChain / LangGraph / CrewAI

```python
from amo.wrappers import LangChainTracer, CrewAITracer

# LangChain — pass as a callback
chain = my_chain.with_config(callbacks=[LangChainTracer()])

# CrewAI — wrap the crew
crew = CrewAITracer(crew).wrap()
```

### Self-host

```bash
git clone https://github.com/your-org/amo
cd amo
docker compose -f infra/docker-compose.yml up
```

Open `http://localhost:3000` — the dashboard is ready.

---

## Roadmap

### MVP (current focus)
- [x] Project structure and architecture docs
- [ ] Python SDK — `@trace` decorator + event models
- [ ] LangChain, LangGraph, CrewAI wrappers
- [ ] Kafka ingestion pipeline
- [ ] ClickHouse trace storage + TimescaleDB metrics storage
- [ ] FastAPI REST API
- [ ] React dashboard — DAG view, cost, failures
- [ ] Docker Compose self-host packaging

### Phase 2
- [ ] JavaScript / TypeScript SDK
- [ ] Eval engine — automated quality scoring
- [ ] Kubernetes manifests
- [ ] OAuth2 / SSO auth
- [ ] Alert rules UI

---

## Requirements

See [REQUIREMENTS.md](REQUIREMENTS.md) for functional and non-functional requirements.

---

## Contributing

AMO is in early development. Architecture decisions and conventions are documented in [CLAUDE.md](CLAUDE.md) (for AI-assisted development) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## License

MIT

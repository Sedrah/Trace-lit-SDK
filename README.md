# Trace-lit — Agent Monitoring & Observability

**Visibility into your AI agents — for everyone, not just developers.**

Trace-lit is an open-source monitoring platform for AI agent orchestration. It gives product managers, ops teams, and business stakeholders a clear view of what their AI agents are doing: where they succeed, where they fail, what they cost, and why.

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
│  SDK Layer (Tracelit-SDK)                         │
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
pip install "Tracelit-SDK[kafka] @ git+https://github.com/Trace-lit/Trace-lit-SDK.git#subdirectory=sdk/python"
```

### 2. Instrument your agent
```python
import trace_lit

trace_lit.configure(
    kafka_brokers=["49.13.235.169:9093"],
    api_key="your-api-key",  # request one from the Trace-lit team
)

@trace_lit.trace(agent_name="my-agent", framework="langchain")
def my_agent(query: str) -> str:
    # your existing code unchanged
    ...
```

### 3. View your dashboard
```
http://49.13.235.169
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
# Trace-lit

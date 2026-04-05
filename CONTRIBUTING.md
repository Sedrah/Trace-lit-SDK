# Contributing to AMO

## Development Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Docker Desktop
- `pip` (or `uv`)

### 1. Clone and install

```bash
git clone https://github.com/Sedrah/AMO.git
cd AMO

# SDK
pip install -e "sdk/python[dev]"

# Ingestion pipeline
pip install -e "ingestion/"

# API
pip install -e "api/"

# Dashboard
cd dashboard/web && npm install
```

### 2. Start infra

```bash
docker compose -f infra/docker-compose.dev.yml up -d
```

### 3. Run tests

```bash
# SDK (no infra needed)
cd sdk/python && pytest -v

# Ingestion (no infra needed)
cd ingestion && pytest -v

# API (no infra needed)
cd api && pytest -v
```

---

## Project Structure

```
sdk/python/          # Tracelit-SDK Python package (@trace, emitter, wrappers)
ingestion/           # Kafka consumer + ClickHouse/TimescaleDB writers
api/                 # FastAPI REST server
dashboard/web/       # React + TypeScript frontend
infra/               # Docker Compose, nginx, ClickHouse config, init SQL
storage/             # Schema migration files (source of truth)
examples/            # Usage examples and test scripts
```

---

## Conventions

### Python
- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy --strict` (SDK only)
- Min Python: 3.9

### TypeScript
- Formatter/linter: Biome
- `npm run dev` for hot reload

### Commits
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` no behaviour change

---

## Key Design Rules

- **`org_id` on every schema** — every ClickHouse table, TimescaleDB table, and API response must include `org_id`. This is the #1 SaaS migration rule.
- **SDK is non-blocking** — the emitter runs on a background daemon thread. Never add synchronous I/O to the hot path.
- **No stack traces in the dashboard** — the API global exception handler strips all internal errors. Keep it that way.
- **API key → org_id server-side** — the SDK never knows its own `org_id`. It sends `api_key` in Kafka headers; the pipeline resolves the mapping.
- **ClickHouse aggregates** — CH 24.x rejects aggregate expressions inside other expressions in SELECT. Derive computed fields (e.g. `status`) in Python from raw aggregate columns.

---

## Opening a PR

1. Branch from `main`
2. Keep PRs focused — one feature or fix per PR
3. All tests must pass
4. Update relevant docs if behaviour changes

# Contributing to Trace-lit

## Development Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Docker Desktop
- `pip` (or `uv`)

### 1. Clone and install

```bash
git clone https://github.com/Sedrah/Trace-lit-SDK.git
cd Trace-lit-SDK

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

## Opening a PR

1. **Open an issue first** — describe what you want to change and why. This avoids wasted effort on PRs that won't be merged.
2. Branch from `main` and submit your PR against `main` only.
3. Keep PRs focused — one feature or fix per PR.
4. All tests must pass.
5. Update relevant docs if behaviour changes.

PRs are reviewed within 5 business days.

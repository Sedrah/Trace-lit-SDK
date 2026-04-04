#!/usr/bin/env bash
# AMO — convenience start script for self-hosted deployment.
#
# Usage:
#   ./scripts/start.sh          # start all services
#   ./scripts/start.sh --dev    # start infra only (for local service dev)
#   ./scripts/start.sh stop     # stop all services
#   ./scripts/start.sh logs     # tail logs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
ENV_FILE="$ROOT/.env"
COMPOSE_PROD="$ROOT/infra/docker-compose.yml"
COMPOSE_DEV="$ROOT/infra/docker-compose.dev.yml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { echo "[AMO] $*"; }
error() { echo "[AMO] ERROR: $*" >&2; exit 1; }

check_deps() {
    command -v docker  >/dev/null 2>&1 || error "docker is not installed."
    docker compose version >/dev/null 2>&1 || error "docker compose plugin not found."
}

ensure_env() {
    if [[ ! -f "$ENV_FILE" ]]; then
        info ".env not found — copying from .env.example"
        cp "$ROOT/.env.example" "$ENV_FILE"
        info "Edit $ENV_FILE before going to production."
    fi
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_start_prod() {
    ensure_env
    info "Starting production stack..."
    docker compose -f "$COMPOSE_PROD" --env-file "$ENV_FILE" up -d --build
    info "AMO is running. Open http://localhost"
}

cmd_start_dev() {
    info "Starting dev infra (Kafka, ClickHouse, TimescaleDB)..."
    docker compose -f "$COMPOSE_DEV" up -d
    info "Infra ready. Start services locally:"
    info "  cd api       && uvicorn server.main:app --reload --port 8000"
    info "  cd ingestion && python -m pipeline.main"
    info "  cd dashboard/web && npm run dev"
}

cmd_stop() {
    info "Stopping services..."
    docker compose -f "$COMPOSE_PROD" down 2>/dev/null || true
    docker compose -f "$COMPOSE_DEV"  down 2>/dev/null || true
    info "Done."
}

cmd_logs() {
    docker compose -f "$COMPOSE_PROD" logs -f --tail=100
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

check_deps

case "${1:-start}" in
    start)   cmd_start_prod ;;
    --dev)   cmd_start_dev  ;;
    stop)    cmd_stop       ;;
    logs)    cmd_logs       ;;
    *)       error "Unknown command: $1. Use: start | --dev | stop | logs" ;;
esac

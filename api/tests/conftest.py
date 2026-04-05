"""
Test fixtures for the AMO API.

We use FastAPI's TestClient with mocked DB connections so tests run without
real ClickHouse or TimescaleDB instances.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server.config import ApiConfig
from server.main import create_app


class MockCHClient:
    """Minimal ClickHouse client mock."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self._results: dict[str, Any] = {}

    def set_result(self, contains: str, rows: list[Any], columns: list[str]) -> None:
        self._results[contains] = (rows, columns)

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> Any:
        self.queries.append(sql)
        for key, (rows, cols) in self._results.items():
            if key in sql:
                result = MagicMock()
                result.result_rows = rows
                result.column_names = cols
                result.first_row = rows[0] if rows else [0]
                return result
        result = MagicMock()
        result.result_rows = []
        result.column_names = []
        result.first_row = [0]
        return result


class MockPGPool:
    """Minimal asyncpg pool mock."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        return [_DictRecord(r) for r in self._rows]

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        if self._rows:
            return _DictRecord(self._rows[0])
        return None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return len(self._rows)

    async def execute(self, sql: str, *args: Any) -> str:
        return "DELETE 1" if self._rows else "DELETE 0"

    async def close(self) -> None:
        pass


class _DictRecord(dict):
    """asyncpg Record-like object backed by a plain dict."""
    pass


@pytest.fixture()
def ch_client() -> MockCHClient:
    return MockCHClient()


@pytest.fixture()
def pg_pool() -> MockPGPool:
    return MockPGPool()


@pytest.fixture()
def client(ch_client: MockCHClient, pg_pool: MockPGPool) -> TestClient:
    cfg = ApiConfig(
        clickhouse_host="mock",
        timescale_dsn="postgresql://mock/mock",
    )

    import os
    os.environ["TRACELIT_ALLOW_KEYLESS"] = "true"

    app = create_app(cfg)

    # Inject mocks into app state before the TestClient starts
    app.state.ch_client = ch_client
    app.state.pg_pool = pg_pool

    # Prevent real DB connections during startup
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    return TestClient(app)

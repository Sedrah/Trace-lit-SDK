from __future__ import annotations

import json
import pytest

from amo.models import TraceEvent
from pipeline.normalizer import Normalizer, _extract_api_key
from tests.conftest import TEST_API_KEY, TEST_ORG_ID


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_normalize_success(
    normalizer: Normalizer,
    valid_payload: bytes,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    result = normalizer.normalize(valid_payload, valid_headers)
    assert result is not None
    assert result.org_id == TEST_ORG_ID
    assert result.agent_name == "test-agent"
    assert result.action == "test-action"


def test_normalize_sets_org_id(
    normalizer: Normalizer,
    valid_payload: bytes,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    result = normalizer.normalize(valid_payload, valid_headers)
    assert result is not None
    assert result.org_id == TEST_ORG_ID  # resolved from api_key, not left as "default"


def test_normalize_calculates_cost(
    normalizer: Normalizer,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    event = TraceEvent(
        agent_name="bot", action="llm_call",
        model="gpt-4o-mini", input_tokens=10_000, output_tokens=5_000,
    )
    result = normalizer.normalize(event.to_kafka_payload(), valid_headers)
    assert result is not None
    assert result.cost_usd > 0.0


def test_normalize_does_not_overwrite_existing_cost(
    normalizer: Normalizer,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    event = TraceEvent(
        agent_name="bot", action="run",
        model="gpt-4o", input_tokens=100, output_tokens=100, cost_usd=0.99,
    )
    result = normalizer.normalize(event.to_kafka_payload(), valid_headers)
    assert result is not None
    assert result.cost_usd == pytest.approx(0.99)


def test_normalize_keyless_self_host(normalizer: Normalizer) -> None:
    event = TraceEvent(agent_name="bot", action="run")
    result = normalizer.normalize(event.to_kafka_payload(), headers=[])
    assert result is not None
    assert result.org_id == "default"  # empty api_key → "default" org


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------

def test_reject_malformed_json(
    normalizer: Normalizer,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    result = normalizer.normalize(b"{not valid json", valid_headers)
    assert result is None
    assert normalizer.stats["rejected_schema"] == 1


def test_reject_missing_required_fields(
    normalizer: Normalizer,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    # Missing agent_name and action
    payload = json.dumps({"trace_id": "00000000-0000-0000-0000-000000000000"}).encode()
    result = normalizer.normalize(payload, valid_headers)
    assert result is None
    assert normalizer.stats["rejected_schema"] == 1


def test_reject_unknown_api_key(
    normalizer: Normalizer,
    valid_payload: bytes,
) -> None:
    headers = [("X-AMO-API-Key", b"sk-unknown-key")]
    result = normalizer.normalize(valid_payload, headers)
    assert result is None
    assert normalizer.stats["rejected_auth"] == 1


def test_stats_track_accepted_and_rejected(
    normalizer: Normalizer,
    valid_payload: bytes,
    valid_headers: list[tuple[str, bytes]],
) -> None:
    normalizer.normalize(valid_payload, valid_headers)  # accepted
    normalizer.normalize(b"bad json", valid_headers)    # rejected schema
    normalizer.normalize(valid_payload, [("X-AMO-API-Key", b"sk-bad")])  # rejected auth

    assert normalizer.stats == {
        "accepted": 1,
        "rejected_schema": 1,
        "rejected_auth": 1,
    }


# ---------------------------------------------------------------------------
# Header extraction
# ---------------------------------------------------------------------------

def test_extract_api_key_present() -> None:
    headers = [("X-AMO-API-Key", b"sk-abc")]
    assert _extract_api_key(headers) == "sk-abc"


def test_extract_api_key_missing() -> None:
    assert _extract_api_key([]) == ""
    assert _extract_api_key(None) == ""


def test_extract_api_key_wrong_header() -> None:
    headers = [("Authorization", b"Bearer token")]
    assert _extract_api_key(headers) == ""

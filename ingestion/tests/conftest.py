from __future__ import annotations

import json
from uuid import uuid4

import pytest

from amo.models import TraceEvent
from pipeline.api_keys import ApiKeyResolver
from pipeline.normalizer import Normalizer


TEST_API_KEY = "sk-test-key"
TEST_ORG_ID  = "org-test"


@pytest.fixture()
def resolver() -> ApiKeyResolver:
    r = ApiKeyResolver({"": "default"})
    r.add(TEST_API_KEY, TEST_ORG_ID)
    return r


@pytest.fixture()
def normalizer(resolver: ApiKeyResolver) -> Normalizer:
    return Normalizer(resolver)


@pytest.fixture()
def valid_event() -> TraceEvent:
    return TraceEvent(
        agent_name="test-agent",
        action="test-action",
        input_tokens=100,
        output_tokens=50,
        model="gpt-4o",
    )


@pytest.fixture()
def valid_payload(valid_event: TraceEvent) -> bytes:
    return valid_event.to_kafka_payload()


@pytest.fixture()
def valid_headers() -> list[tuple[str, bytes]]:
    return [("X-AMO-API-Key", TEST_API_KEY.encode())]

"""
Normalizer: transforms a raw Kafka message into a fully-enriched TraceEvent.

Responsibilities:
  1. Deserialize the raw JSON payload
  2. Validate against the TraceEvent schema
  3. Resolve api_key (from Kafka message headers) → org_id
  4. Calculate cost_usd from tokens + model pricing
  5. Return the enriched event — or None if the message should be rejected

Rejected messages are logged and counted; they are NOT retried (offset is still committed).
Malformed events sent to a dead-letter topic is a phase 2 concern.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import ValidationError

from amo.models import TraceEvent

from .api_keys import ApiKeyResolver
from .cost import calculate_cost

logger = logging.getLogger("amo.pipeline")


class Normalizer:
    def __init__(self, resolver: ApiKeyResolver) -> None:
        self._resolver = resolver
        self._accepted = 0
        self._rejected_schema = 0
        self._rejected_auth = 0

    def normalize(
        self,
        payload: bytes,
        headers: list[tuple[str, bytes]] | None,
    ) -> Optional[TraceEvent]:
        """
        Parse and enrich a raw Kafka message.

        Args:
            payload: UTF-8 JSON bytes from the Kafka message value.
            headers: Kafka message headers list of (key, value_bytes) tuples.
                     Expected to contain 'X-AMO-API-Key'.

        Returns:
            Enriched TraceEvent with org_id and cost_usd populated,
            or None if the message is invalid and should be skipped.
        """
        # 1. Deserialize
        try:
            raw = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._rejected_schema += 1
            logger.warning("AMO normalizer: malformed JSON — skipping: %s", exc)
            return None

        # 2. Validate schema
        try:
            event = TraceEvent.model_validate(raw)
        except ValidationError as exc:
            self._rejected_schema += 1
            logger.warning(
                "AMO normalizer: schema validation failed — skipping: %s",
                exc.error_count(),
            )
            return None

        # 3. Resolve org_id from api_key header
        api_key = _extract_api_key(headers)
        org_id = self._resolver.resolve(api_key)
        if org_id is None:
            self._rejected_auth += 1
            logger.warning(
                "AMO normalizer: unrecognised api_key (redacted) — rejecting span %s",
                event.span_id,
            )
            return None

        # 4. Calculate cost if not already set by the SDK
        cost = event.cost_usd
        if cost == 0.0 and (event.input_tokens > 0 or event.output_tokens > 0):
            cost = calculate_cost(event.model, event.input_tokens, event.output_tokens)

        # 5. Return enriched, immutable event
        self._accepted += 1
        return event.model_copy(update={"org_id": org_id, "cost_usd": cost})

    @property
    def stats(self) -> dict[str, int]:
        return {
            "accepted": self._accepted,
            "rejected_schema": self._rejected_schema,
            "rejected_auth": self._rejected_auth,
        }


def _extract_api_key(headers: list[tuple[str, bytes]] | None) -> str:
    """Pull the api_key from Kafka message headers. Returns '' if not present."""
    if not headers:
        return ""
    for key, value in headers:
        if key == "X-AMO-API-Key":
            try:
                return value.decode()
            except Exception:
                return ""
    return ""

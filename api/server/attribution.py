"""
Failure attribution engine — pure Python, no DB calls.

Works on a list of span dicts (already fetched from ClickHouse).
Identifies root cause failures vs cascades, and classifies each
root cause with a human-readable reason.

Design:
  - A span is a ROOT CAUSE if its parent span did NOT fail (or has no parent)
  - A span is a CASCADE if its parent span also failed
  - Classification is rule-based — no LLM needed, fully air-gapped
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Rule-based classifier
# ---------------------------------------------------------------------------

def _classify(error_type: str, error_msg: str) -> tuple[str, str]:
    """Returns (classification_slug, human_readable_description)."""
    msg = (error_msg or "").lower()
    etype = (error_type or "").lower()

    if "timeout" in msg or "timed out" in msg or "deadline" in msg:
        return "llm_timeout", "LLM did not respond in time"
    if "rate limit" in msg or "ratelimit" in etype or "429" in msg or "too many requests" in msg:
        return "rate_limit", "LLM API rate limit exceeded"
    if "context length" in msg or ("token" in msg and "limit" in msg) or "maximum context" in msg or "context window" in msg:
        return "context_length_exceeded", "Input exceeded the model's context window"
    if ("empty" in msg or "none" in msg or "null" in msg) and ("result" in msg or "response" in msg or "output" in msg):
        return "tool_empty_result", "Tool returned an empty result"
    if "connection" in msg or "network" in msg or "unreachable" in msg or "refused" in msg or "econnrefused" in msg:
        return "network_error", "Network connection failed"
    if "auth" in msg or "unauthorized" in msg or "forbidden" in msg or "403" in msg or "401" in msg:
        return "auth_error", "Authentication or permission error"
    if "valueerror" in etype or "typeerror" in etype or "invalid" in msg:
        return "invalid_input", "Invalid input or type mismatch"
    if "tool" in etype or "toolexception" in etype or "tool" in msg:
        return "tool_call_failed", "Tool call returned an error"
    if "memoryerror" in etype or "out of memory" in msg:
        return "out_of_memory", "Process ran out of memory"
    return "unknown_error", "Unexpected error — check the agent logs"


# ---------------------------------------------------------------------------
# Attribution engine
# ---------------------------------------------------------------------------

def attribute_failures(spans: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Given all spans for a trace, return a structured attribution result.

    Returns a dict matching the AttributionResponse model shape.
    """
    error_spans: dict[Any, dict[str, Any]] = {
        s["span_id"]: s for s in spans if s.get("status") == "error"
    }

    if not error_spans:
        return {"has_failures": False, "root_causes": [], "cascades": []}

    root_causes = []
    cascades = []

    for span_id, span in error_spans.items():
        parent_id = span.get("parent_span_id")
        parent_failed = bool(parent_id and parent_id in error_spans)

        if parent_failed:
            cascades.append({
                "span_id": str(span_id),
                "agent_name": span["agent_name"],
                "action": span["action"],
                "caused_by_span_id": str(parent_id),
                "caused_by_agent": error_spans[parent_id]["agent_name"],
                "caused_by_action": error_spans[parent_id]["action"],
            })
        else:
            # Find spans that directly cascaded from this root cause
            cascaded_to = [
                str(s["span_id"])
                for s in error_spans.values()
                if s.get("parent_span_id") == span_id
            ]
            classification, description = _classify(
                span.get("error_type") or "",
                span.get("error_msg") or "",
            )
            root_causes.append({
                "span_id": str(span_id),
                "agent_name": span["agent_name"],
                "action": span["action"],
                "classification": classification,
                "description": description,
                "cascaded_to": cascaded_to,
            })

    return {
        "has_failures": True,
        "root_causes": root_causes,
        "cascades": cascades,
    }

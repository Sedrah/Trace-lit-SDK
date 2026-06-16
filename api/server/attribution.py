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

from trace_lit.attribution_graph import build_attribution_graph


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
    raw_root_causes, cascades = build_attribution_graph(spans)

    if not raw_root_causes and not cascades:
        return {"has_failures": False, "root_causes": [], "cascades": []}

    root_causes = []
    for rc in raw_root_causes:
        classification, description = _classify(rc["error_type"], rc["error_msg"])
        root_causes.append({
            "span_id": str(rc["span_id"]),
            "agent_name": rc["agent_name"],
            "action": rc["action"],
            "classification": classification,
            "description": description,
            "cascaded_to": rc["cascaded_to"],
        })

    return {
        "has_failures": True,
        "root_causes": root_causes,
        "cascades": cascades,
    }

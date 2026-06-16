"""
Attribution graph walk — shared structural logic for failure attribution.

Given a trace's spans, determines which failed spans are root causes
(their parent did not also fail) versus cascades (their parent failed too).
Pure graph logic, no classification — both the free rule-based attribution
engine and the paid LLM-assisted one build on top of this.
"""

from __future__ import annotations

from typing import Any, TypedDict


class RootCauseSpan(TypedDict):
    span_id: Any
    agent_name: str
    action: str
    error_type: str
    error_msg: str
    cascaded_to: list[str]


class CascadeSpan(TypedDict):
    span_id: str
    agent_name: str
    action: str
    caused_by_span_id: str
    caused_by_agent: str
    caused_by_action: str


def build_attribution_graph(
    spans: list[dict[str, Any]],
) -> tuple[list[RootCauseSpan], list[CascadeSpan]]:
    """
    Returns (root_cause_spans, cascades). Root cause spans are returned
    unclassified — callers attach their own classification/description
    (rule-based or LLM-based) on top.
    """
    error_spans: dict[Any, dict[str, Any]] = {
        s["span_id"]: s for s in spans if s.get("status") == "error"
    }

    root_causes: list[RootCauseSpan] = []
    cascades: list[CascadeSpan] = []

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
            cascaded_to = [
                str(s["span_id"])
                for s in error_spans.values()
                if s.get("parent_span_id") == span_id
            ]
            root_causes.append({
                "span_id": span_id,
                "agent_name": span["agent_name"],
                "action": span["action"],
                "error_type": span.get("error_type") or "",
                "error_msg": span.get("error_msg") or "",
                "cascaded_to": cascaded_to,
            })

    return root_causes, cascades

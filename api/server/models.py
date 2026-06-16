"""
API response models — what the REST API returns to callers.

These are separate from trace_lit.models.TraceEvent (the internal event model).
They are shaped for the dashboard and for non-developer readability:
- costs in USD, not tokens alone
- human-readable failure reasons, not error codes
- DAG as nodes + edges ready for React Flow
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    has_more: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

class SpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    span_id: UUID
    parent_span_id: Optional[UUID]
    timestamp: datetime
    duration_ms: int
    agent_name: str
    action: str
    status: str
    framework: str
    model: Optional[str]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error_type: Optional[str]
    error_msg: Optional[str]
    metadata: dict[str, Any]


class TraceResponse(BaseModel):
    trace_id: UUID
    org_id: str
    agent_name: str
    framework: str
    started_at: datetime
    finished_at: datetime
    total_spans: int
    error_spans: int
    total_cost_usd: float
    total_duration_ms: int
    status: str


class TraceDetailResponse(TraceResponse):
    spans: List[SpanResponse]


class TraceListResponse(BaseModel):
    items: List[TraceResponse]
    meta: PageMeta


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

class DAGNode(BaseModel):
    id: str           # span_id as string
    label: str        # "{agent_name} — {action}"
    agent_name: str
    action: str
    status: str
    duration_ms: int
    cost_usd: float
    framework: str
    error_msg: Optional[str]


class DAGEdge(BaseModel):
    source: str       # parent span_id
    target: str       # child span_id
    duration_ms: int  # edge weight = child duration


class DAGResponse(BaseModel):
    trace_id: UUID
    nodes: List[DAGNode]
    edges: List[DAGEdge]


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AgentSummary(BaseModel):
    agent_name: str
    framework: str
    call_count: int
    error_count: int
    error_rate: float        # 0.0–1.0
    avg_duration_ms: float
    total_cost_usd: float
    last_seen: datetime


class AgentListResponse(BaseModel):
    items: List[AgentSummary]
    meta: PageMeta


class MetricPoint(BaseModel):
    bucket: datetime
    total: float
    avg_value: float
    max_value: float
    sample_count: int


class AgentMetricsResponse(BaseModel):
    agent_name: str
    metric_name: str
    granularity: str          # "hourly" | "daily"
    points: List[MetricPoint]


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------

class CostBreakdownItem(BaseModel):
    agent_name: str
    framework: str
    total_cost_usd: float
    call_count: int
    avg_cost_per_call: float


class CostResponse(BaseModel):
    total_cost_usd: float
    period_start: datetime
    period_end: datetime
    breakdown: List[CostBreakdownItem]


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------

class FailureResponse(BaseModel):
    span_id: UUID
    trace_id: UUID
    timestamp: datetime
    agent_name: str
    action: str
    framework: str
    classification: str      # human-readable category
    description: str         # plain-English sentence
    duration_ms: int
    error_type: Optional[str]


class FailureListResponse(BaseModel):
    items: List[FailureResponse]
    meta: PageMeta


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertRuleRequest(BaseModel):
    name: str
    agent_name: Optional[str] = None      # None = applies to all agents
    metric: str                           # "cost_usd" | "error_rate" | "duration_ms"
    threshold: float
    window_minutes: int = 60
    channel: str                          # "slack" | "webhook"
    webhook_url: str


class AlertRuleResponse(AlertRuleRequest):
    id: int
    org_id: str
    created_at: datetime
    enabled: bool


class AlertRuleListResponse(BaseModel):
    items: List[AlertRuleResponse]


# ---------------------------------------------------------------------------
# Failure attribution
# ---------------------------------------------------------------------------

class RootCause(BaseModel):
    span_id: str
    agent_name: str
    action: str
    classification: str       # e.g. "llm_timeout", "tool_empty_result"
    description: str          # plain-English sentence
    cascaded_to: List[str]    # span_ids of spans that failed because of this


class CascadeFailure(BaseModel):
    span_id: str
    agent_name: str
    action: str
    caused_by_span_id: str
    caused_by_agent: str
    caused_by_action: str


class AttributionResponse(BaseModel):
    trace_id: UUID
    has_failures: bool
    root_causes: List[RootCause]
    cascades: List[CascadeFailure]


# ---------------------------------------------------------------------------
# Admin — API key management
# ---------------------------------------------------------------------------

class ApiKeyCreateRequest(BaseModel):
    org_id: str
    name: str
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    id: int
    org_id: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime]
    # key_hash is intentionally excluded — never returned after creation


class ApiKeyCreateResponse(ApiKeyResponse):
    raw_key: str   # returned once at creation, never stored in plaintext


class ApiKeyListResponse(BaseModel):
    items: List[ApiKeyResponse]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

class PromptSummary(BaseModel):
    prompt_name: str
    latest_version: int
    version_count: int
    last_updated_at: datetime


class PromptListResponse(BaseModel):
    items: List[PromptSummary]


class PromptVersionSummary(BaseModel):
    version: int
    prompt_hash: str
    first_seen_at: datetime
    preview: str


class PromptVersionListResponse(BaseModel):
    prompt_name: str
    items: List[PromptVersionSummary]


class PromptVersionDetail(BaseModel):
    version: int
    prompt_hash: str
    first_seen_at: datetime
    content: str


class PromptVersionMetrics(BaseModel):
    span_count: int
    avg_cost_usd: float
    avg_duration_ms: float
    error_rate: float        # 0.0–1.0

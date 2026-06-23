// ---------------------------------------------------------------------------
// Mirrors the FastAPI response models in api/server/models.py
// ---------------------------------------------------------------------------

export interface PageMeta {
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// Traces
export interface TraceResponse {
  trace_id: string;
  org_id: string;
  agent_name: string;
  framework: string;
  started_at: string;
  finished_at: string;
  total_spans: number;
  error_spans: number;
  total_cost_usd: number;
  total_duration_ms: number;
  status: "success" | "error" | "partial";
}

export interface SpanResponse {
  span_id: string;
  parent_span_id: string | null;
  timestamp: string;
  duration_ms: number;
  agent_name: string;
  action: string;
  status: string;
  framework: string;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  error_type: string | null;
  error_msg: string | null;
  metadata: Record<string, unknown>;
  input_text: string | null;
  output_text: string | null;
}

export interface TraceDetailResponse extends TraceResponse {
  spans: SpanResponse[];
}

export interface TraceListResponse {
  items: TraceResponse[];
  meta: PageMeta;
}

// DAG
export interface DAGNode {
  id: string;
  label: string;
  agent_name: string;
  action: string;
  status: string;
  duration_ms: number;
  cost_usd: number;
  framework: string;
  error_msg: string | null;
}

export interface DAGEdge {
  source: string;
  target: string;
  duration_ms: number;
}

export interface DAGResponse {
  trace_id: string;
  nodes: DAGNode[];
  edges: DAGEdge[];
}

// Agents
export interface AgentSummary {
  agent_name: string;
  framework: string;
  call_count: number;
  error_count: number;
  error_rate: number;
  avg_duration_ms: number;
  total_cost_usd: number;
  last_seen: string;
}

export interface AgentListResponse {
  items: AgentSummary[];
  meta: PageMeta;
}

export interface MetricPoint {
  bucket: string;
  total: number;
  avg_value: number;
  max_value: number;
  sample_count: number;
}

export interface AgentMetricsResponse {
  agent_name: string;
  metric_name: string;
  granularity: string;
  points: MetricPoint[];
}

// Costs
export interface CostBreakdownItem {
  agent_name: string;
  framework: string;
  total_cost_usd: number;
  call_count: number;
  avg_cost_per_call: number;
}

export interface CostResponse {
  total_cost_usd: number;
  period_start: string;
  period_end: string;
  breakdown: CostBreakdownItem[];
}

// Failures
export interface FailureResponse {
  span_id: string;
  trace_id: string;
  timestamp: string;
  agent_name: string;
  action: string;
  framework: string;
  classification: string;
  description: string;
  duration_ms: number;
  error_type: string | null;
}

export interface FailureListResponse {
  items: FailureResponse[];
  meta: PageMeta;
}

// Alerts
export interface AlertRuleResponse {
  id: number;
  org_id: string;
  name: string;
  agent_name: string | null;
  metric: string;
  threshold: number;
  window_minutes: number;
  channel: string;
  webhook_url: string;
  enabled: boolean;
  created_at: string;
}

export interface AlertRuleListResponse {
  items: AlertRuleResponse[];
}

export interface AlertRuleRequest {
  name: string;
  agent_name?: string | null;
  metric: string;
  threshold: number;
  window_minutes?: number;
  channel: string;
  webhook_url: string;
}

// Failure attribution
export interface RootCause {
  span_id: string;
  agent_name: string;
  action: string;
  classification: string;
  description: string;
  cascaded_to: string[];
  summary?: string | null;   // populated by Attribution v2 (enterprise), null/absent on v1
}

export interface CascadeFailure {
  span_id: string;
  agent_name: string;
  action: string;
  caused_by_span_id: string;
  caused_by_agent: string;
  caused_by_action: string;
}

export interface AttributionResponse {
  trace_id: string;
  has_failures: boolean;
  root_causes: RootCause[];
  cascades: CascadeFailure[];
}

// Admin — API key management
export interface ApiKeyResponse {
  id: number;
  org_id: string;
  name: string;
  created_at: string;
  expires_at: string | null;
}

export interface ApiKeyCreateResponse extends ApiKeyResponse {
  raw_key: string;
}

export interface ApiKeyListResponse {
  items: ApiKeyResponse[];
}

export interface ApiKeyCreateRequest {
  org_id: string;
  name: string;
  expires_at?: string | null;
}

// Prompts
export interface PromptSummary {
  prompt_name: string;
  latest_version: number;
  version_count: number;
  last_updated_at: string;
}

export interface PromptListResponse {
  items: PromptSummary[];
}

export interface PromptVersionSummary {
  version: number;
  prompt_hash: string;
  first_seen_at: string;
  preview: string;
}

export interface PromptVersionListResponse {
  prompt_name: string;
  items: PromptVersionSummary[];
}

export interface PromptVersionDetail {
  version: number;
  prompt_hash: string;
  first_seen_at: string;
  content: string;
}

export interface PromptVersionMetrics {
  span_count: number;
  avg_cost_usd: number;
  avg_duration_ms: number;
  error_rate: number;
}

// Datasets
export interface DatasetResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  item_count: number;
}

export interface DatasetListResponse {
  items: DatasetResponse[];
}

export interface DatasetItemResponse {
  id: string;
  dataset_id: string;
  trace_id: string;
  span_id: string;
  label: "good" | "bad" | "neutral";
  notes: string | null;
  agent_name: string | null;
  action: string | null;
  model: string | null;
  input_text: string | null;
  output_text: string | null;
  created_at: string;
}

export interface DatasetItemListResponse {
  dataset: DatasetResponse;
  items: DatasetItemResponse[];
}

/**
 * AMO API client.
 *
 * All requests go to /api/v1 (proxied to localhost:8000 by Vite in dev).
 * The API key is read from localStorage so users only need to enter it once.
 */

import type {
  AgentListResponse,
  AgentMetricsResponse,
  AlertRuleListResponse,
  AlertRuleRequest,
  AlertRuleResponse,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  ApiKeyListResponse,
  AttributionResponse,
  CostResponse,
  DAGResponse,
  FailureListResponse,
  TraceDetailResponse,
  TraceListResponse,
} from "../types";

const BASE = "/api/v1";

export function getApiKey(): string {
  return localStorage.getItem("trace_lit_api_key") ?? "";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const key = getApiKey();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-Tracelit-Api-Key": key } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText, body.detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: string,
  ) {
    super(message);
  }
}

// ---------------------------------------------------------------------------
// Traces
// ---------------------------------------------------------------------------

export function getTraces(params: URLSearchParams): Promise<TraceListResponse> {
  return request(`/traces?${params}`);
}

export function getTrace(traceId: string): Promise<TraceDetailResponse> {
  return request(`/traces/${traceId}`);
}

export function getDag(traceId: string): Promise<DAGResponse> {
  return request(`/traces/${traceId}/dag`);
}

export function getAttribution(traceId: string): Promise<AttributionResponse> {
  return request(`/traces/${traceId}/attribution`);
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export function getAgents(params: URLSearchParams): Promise<AgentListResponse> {
  return request(`/agents?${params}`);
}

export function getAgentMetrics(
  agentName: string,
  params: URLSearchParams,
): Promise<AgentMetricsResponse> {
  return request(`/agents/${encodeURIComponent(agentName)}/metrics?${params}`);
}

// ---------------------------------------------------------------------------
// Costs
// ---------------------------------------------------------------------------

export function getCosts(params: URLSearchParams): Promise<CostResponse> {
  return request(`/costs?${params}`);
}

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------

export function getFailures(
  params: URLSearchParams,
): Promise<FailureListResponse> {
  return request(`/failures?${params}`);
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export function getAlerts(): Promise<AlertRuleListResponse> {
  return request("/alerts");
}

export function createAlert(
  body: AlertRuleRequest,
): Promise<AlertRuleResponse> {
  return request("/alerts", { method: "POST", body: JSON.stringify(body) });
}

export function deleteAlert(id: number): Promise<void> {
  return request(`/alerts/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// API key helpers (used by Settings / ApiKeyGate)
// ---------------------------------------------------------------------------

export function saveApiKey(key: string): void {
  localStorage.setItem("trace_lit_api_key", key);
}

export function clearApiKey(): void {
  localStorage.removeItem("trace_lit_api_key");
}

export function hasApiKey(): boolean {
  return Boolean(localStorage.getItem("trace_lit_api_key"));
}

// ---------------------------------------------------------------------------
// Admin — API key management
// ---------------------------------------------------------------------------

function adminRequest<T>(
  path: string,
  adminKey: string,
  options: RequestInit = {},
): Promise<T> {
  return request(path, {
    ...options,
    headers: {
      "X-Tracelit-Admin-Key": adminKey,
      ...((options.headers as Record<string, string>) ?? {}),
    },
  });
}

export function listAdminKeys(
  adminKey: string,
  orgId?: string,
): Promise<ApiKeyListResponse> {
  const qs = orgId ? `?org_id=${encodeURIComponent(orgId)}` : "";
  return adminRequest(`/admin/keys${qs}`, adminKey);
}

export function createAdminKey(
  adminKey: string,
  body: ApiKeyCreateRequest,
): Promise<ApiKeyCreateResponse> {
  return adminRequest("/admin/keys", adminKey, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteAdminKey(adminKey: string, keyId: number): Promise<void> {
  return adminRequest(`/admin/keys/${keyId}`, adminKey, { method: "DELETE" });
}

export function saveAdminKey(key: string): void {
  localStorage.setItem("trace_lit_admin_key", key);
}

export function clearAdminKey(): void {
  localStorage.removeItem("trace_lit_admin_key");
}

export function getStoredAdminKey(): string {
  return localStorage.getItem("trace_lit_admin_key") ?? "";
}

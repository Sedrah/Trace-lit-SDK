/**
 * TanStack Query hooks — one per API endpoint.
 * All hooks accept a `params` object that maps to URLSearchParams.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./client";

type Params = Record<string, string | number | boolean | undefined>;

function toSearch(p: Params): URLSearchParams {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) {
    if (v !== undefined && v !== "") sp.set(k, String(v));
  }
  return sp;
}

// ---------------------------------------------------------------------------
// Traces
// ---------------------------------------------------------------------------

export function useTraces(params: Params) {
  return useQuery({
    queryKey: ["traces", params],
    queryFn: () => api.getTraces(toSearch(params)),
  });
}

export function useTrace(traceId: string) {
  return useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => api.getTrace(traceId),
    enabled: Boolean(traceId),
  });
}

export function useDag(traceId: string) {
  return useQuery({
    queryKey: ["dag", traceId],
    queryFn: () => api.getDag(traceId),
    enabled: Boolean(traceId),
  });
}

export function useAttribution(traceId: string, hasFailures: boolean) {
  return useQuery({
    queryKey: ["attribution", traceId],
    queryFn: () => api.getAttribution(traceId),
    enabled: Boolean(traceId) && hasFailures,
  });
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export function useAgents(params: Params) {
  return useQuery({
    queryKey: ["agents", params],
    queryFn: () => api.getAgents(toSearch(params)),
  });
}

export function useAgentMetrics(agentName: string, params: Params) {
  return useQuery({
    queryKey: ["agent-metrics", agentName, params],
    queryFn: () => api.getAgentMetrics(agentName, toSearch(params)),
    enabled: Boolean(agentName),
  });
}

// ---------------------------------------------------------------------------
// Costs
// ---------------------------------------------------------------------------

export function useCosts(params: Params) {
  return useQuery({
    queryKey: ["costs", params],
    queryFn: () => api.getCosts(toSearch(params)),
  });
}

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------

export function useFailures(params: Params) {
  return useQuery({
    queryKey: ["failures", params],
    queryFn: () => api.getFailures(toSearch(params)),
  });
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: api.getAlerts,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

// ---------------------------------------------------------------------------
// Admin — API key management
// ---------------------------------------------------------------------------

export function useAdminKeys(adminKey: string, orgId?: string) {
  return useQuery({
    queryKey: ["admin-keys", adminKey, orgId],
    queryFn: () => api.listAdminKeys(adminKey, orgId),
    enabled: Boolean(adminKey),
    retry: false,
  });
}

export function useCreateAdminKey(adminKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof api.createAdminKey>[1]) =>
      api.createAdminKey(adminKey, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-keys"] }),
  });
}

export function useDeleteAdminKey(adminKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: number) => api.deleteAdminKey(adminKey, keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-keys"] }),
  });
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

export function usePrompts() {
  return useQuery({
    queryKey: ["prompts"],
    queryFn: api.getPrompts,
  });
}

export function usePromptVersions(promptName: string) {
  return useQuery({
    queryKey: ["prompt-versions", promptName],
    queryFn: () => api.getPromptVersions(promptName),
    enabled: Boolean(promptName),
  });
}

export function usePromptVersion(promptName: string, version: number | null) {
  return useQuery({
    queryKey: ["prompt-version", promptName, version],
    queryFn: () => api.getPromptVersion(promptName, version as number),
    enabled: Boolean(promptName) && version !== null,
  });
}

export function usePromptVersionMetrics(
  promptName: string,
  version: number | null,
) {
  return useQuery({
    queryKey: ["prompt-version-metrics", promptName, version],
    queryFn: () => api.getPromptVersionMetrics(promptName, version as number),
    enabled: Boolean(promptName) && version !== null,
  });
}

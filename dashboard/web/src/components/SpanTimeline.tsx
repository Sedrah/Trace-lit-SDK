/**
 * Step table — spans sorted in execution order (parent before children),
 * displayed as a readable table with status, action, agent, model,
 * duration, tokens, and cost.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDatasets, addDatasetItem } from "../api/client";
import type { DatasetResponse, SpanResponse } from "../types";
import { formatCost, formatDuration } from "./ui";

/** Topological sort: root spans first, then children in timestamp order. */
function sortSpans(spans: SpanResponse[]): SpanResponse[] {
  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const children = new Map<string | null, SpanResponse[]>();

  for (const s of spans) {
    const p = s.parent_span_id ?? null;
    if (!children.has(p)) children.set(p, []);
    children.get(p)!.push(s);
  }

  // Sort each sibling group by timestamp
  for (const [, group] of children) {
    group.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }

  // Only include roots whose parent doesn't exist in the span set
  const roots = (children.get(null) ?? []).filter((s) => !byId.has(s.parent_span_id!));

  const result: SpanResponse[] = [];
  function walk(span: SpanResponse) {
    result.push(span);
    for (const child of children.get(span.span_id) ?? []) walk(child);
  }
  for (const root of roots) walk(root);

  // Append any orphaned spans not reached by the walk
  const visited = new Set(result.map((s) => s.span_id));
  for (const s of spans) if (!visited.has(s.span_id)) result.push(s);

  return result;
}

function getDepth(spanId: string, parentMap: Record<string, string | null>, cache: Record<string, number>): number {
  if (spanId in cache) return cache[spanId];
  const p = parentMap[spanId];
  const d = p && p in parentMap ? getDepth(p, parentMap, cache) + 1 : 0;
  cache[spanId] = d;
  return d;
}

const STATUS_COLOURS: Record<string, { dot: string; row: string }> = {
  success: { dot: "bg-green-400",  row: "" },
  error:   { dot: "bg-red-500",    row: "bg-red-50/40" },
  timeout: { dot: "bg-yellow-400", row: "bg-yellow-50/40" },
};

// ---------------------------------------------------------------------------
// Inline "Add to dataset" picker — shown on span row hover
// ---------------------------------------------------------------------------

function AddToDataset({ span, traceId }: { span: SpanResponse; traceId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [datasetId, setDatasetId] = useState("");
  const [label, setLabel] = useState<"good" | "bad" | "neutral">("good");
  const [notes, setNotes] = useState("");
  const [done, setDone] = useState(false);

  const { data } = useQuery({ queryKey: ["datasets"], queryFn: getDatasets, enabled: open });

  const mutation = useMutation({
    mutationFn: () =>
      addDatasetItem(datasetId, {
        trace_id: traceId,
        span_id: span.span_id,
        label,
        notes: notes.trim() || undefined,
        agent_name: span.agent_name,
        action: span.action,
        model: span.model,
        input_text: span.input_text,
        output_text: span.output_text,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dataset-items", datasetId] });
      qc.invalidateQueries({ queryKey: ["datasets"] });
      setDone(true);
      setTimeout(() => { setOpen(false); setDone(false); setNotes(""); }, 1200);
    },
  });

  if (done) return <span className="text-xs text-green-600">Added</span>;

  return (
    <div className="relative" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs px-2 py-0.5 border border-gray-200 rounded text-gray-500 hover:border-brand-400 hover:text-brand-600 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        + Dataset
      </button>
      {open && (
        <div className="absolute right-0 top-6 z-50 w-56 bg-white border border-gray-200 rounded-lg shadow-lg p-3 space-y-2">
          <p className="text-xs font-semibold text-gray-700">Add to dataset</p>
          <select
            value={datasetId}
            onChange={e => setDatasetId(e.target.value)}
            className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">— pick a dataset —</option>
            {data?.items.map((ds: DatasetResponse) => (
              <option key={ds.id} value={ds.id}>{ds.name}</option>
            ))}
          </select>
          <div className="flex gap-1">
            {(["good", "bad", "neutral"] as const).map(l => (
              <button
                key={l}
                onClick={() => setLabel(l)}
                className={`flex-1 text-xs py-1 rounded border ${
                  label === l
                    ? l === "good" ? "bg-green-100 border-green-400 text-green-700"
                      : l === "bad" ? "bg-red-100 border-red-400 text-red-700"
                      : "bg-gray-100 border-gray-400 text-gray-600"
                    : "border-gray-200 text-gray-400 hover:border-gray-400"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Notes (optional)"
            className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            onClick={() => mutation.mutate()}
            disabled={!datasetId || mutation.isPending}
            className="w-full text-xs py-1.5 bg-brand-600 text-white rounded hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Adding…" : "Add"}
          </button>
        </div>
      )}
    </div>
  );
}

export function SpanTimeline({ spans, traceId }: { spans: SpanResponse[]; totalMs: number; traceId: string }) {
  if (spans.length === 0) return null;

  const [expanded, setExpanded] = useState<string | null>(null);

  const sorted = sortSpans(spans);
  const parentMap = Object.fromEntries(sorted.map((s) => [s.span_id, s.parent_span_id ?? null]));
  const depthCache: Record<string, number> = {};

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs text-gray-400 font-medium uppercase tracking-wide">
            <th className="px-4 py-2 text-left w-8">#</th>
            <th className="px-4 py-2 text-left">Step</th>
            <th className="px-4 py-2 text-left">Agent</th>
            <th className="px-4 py-2 text-left">Model</th>
            <th className="px-4 py-2 text-right">Duration</th>
            <th className="px-4 py-2 text-right">Tokens in / out</th>
            <th className="px-4 py-2 text-right">Cost</th>
            <th className="px-4 py-2 w-20" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((span, idx) => {
            const depth = getDepth(span.span_id, parentMap, depthCache);
            const { dot, row } = STATUS_COLOURS[span.status] ?? { dot: "bg-gray-400", row: "" };
            const hasTokens = span.input_tokens > 0 || span.output_tokens > 0;
            const hasIO = !!(span.input_text || span.output_text);
            const isExpanded = expanded === span.span_id;

            return (
              <>
                <tr
                  key={span.span_id}
                  onClick={() => hasIO && setExpanded(isExpanded ? null : span.span_id)}
                  className={`border-b border-gray-100 group ${hasIO ? "cursor-pointer" : ""} hover:bg-gray-50 ${row}`}
                >
                  <td className="px-4 py-2.5 text-xs text-gray-300 font-mono">{idx + 1}</td>

                  {/* Step name — indented by depth */}
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 }}>
                      {depth > 0 && <span className="text-gray-300 text-xs">↳</span>}
                      <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                      <span className="font-medium text-gray-900">{span.action}</span>
                      {hasIO && (
                        <span className="text-xs text-gray-400 ml-1">{isExpanded ? "▴" : "▾"}</span>
                      )}
                    </div>
                    {span.error_msg && (
                      <p className="text-xs text-red-500 mt-0.5 pl-6" style={{ paddingLeft: depth * 20 + 24 }}>
                        {span.error_msg}
                      </p>
                    )}
                  </td>

                  <td className="px-4 py-2.5 text-gray-500 text-xs">{span.agent_name}</td>

                  <td className="px-4 py-2.5">
                    {span.model ? (
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">
                        {span.model}
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  <td className="px-4 py-2.5 text-right text-gray-600 tabular-nums">
                    {formatDuration(span.duration_ms)}
                  </td>

                  <td className="px-4 py-2.5 text-right text-gray-500 tabular-nums text-xs">
                    {hasTokens
                      ? `${span.input_tokens.toLocaleString()} / ${span.output_tokens.toLocaleString()}`
                      : <span className="text-gray-300">—</span>}
                  </td>

                  <td className="px-4 py-2.5 text-right font-mono text-gray-600 text-xs">
                    {span.cost_usd > 0 ? formatCost(span.cost_usd) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <AddToDataset span={span} traceId={traceId} />
                  </td>
                </tr>
                {isExpanded && (
                  <tr key={`${span.span_id}-io`} className="bg-gray-50 border-b border-gray-200">
                    <td />
                    <td colSpan={7} className="px-4 py-3 space-y-3">
                      {span.input_text && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 mb-1">Input</p>
                          <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words max-h-48">
                            {span.input_text}
                          </pre>
                        </div>
                      )}
                      {span.output_text && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 mb-1">Output</p>
                          <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words max-h-48">
                            {span.output_text}
                          </pre>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

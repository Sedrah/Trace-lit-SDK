/**
 * Step table — spans sorted in execution order (parent before children),
 * displayed as a readable table with status, action, agent, model,
 * duration, tokens, and cost.
 */

import type { SpanResponse } from "../types";
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

export function SpanTimeline({ spans }: { spans: SpanResponse[]; totalMs: number }) {
  if (spans.length === 0) return null;

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
          </tr>
        </thead>
        <tbody>
          {sorted.map((span, idx) => {
            const depth = getDepth(span.span_id, parentMap, depthCache);
            const { dot, row } = STATUS_COLOURS[span.status] ?? { dot: "bg-gray-400", row: "" };
            const hasTokens = span.input_tokens > 0 || span.output_tokens > 0;

            return (
              <>
                <tr
                  key={span.span_id}
                  className={`border-b border-gray-100 hover:bg-gray-50 ${row}`}
                >
                  <td className="px-4 py-2.5 text-xs text-gray-300 font-mono">{idx + 1}</td>

                  {/* Step name — indented by depth */}
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 }}>
                      {depth > 0 && <span className="text-gray-300 text-xs">↳</span>}
                      <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                      <span className="font-medium text-gray-900">{span.action}</span>
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
                </tr>
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

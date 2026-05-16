/**
 * Step log — ordered list of spans, indented by depth.
 * Designed for non-developers: action name, agent, duration, tokens, cost.
 * No bars — numbers speak louder than proportional widths at mixed scales.
 */

import type { SpanResponse } from "../types";
import { formatCost, formatDuration } from "./ui";

function getDepth(
  spanId: string,
  parentMap: Record<string, string | null>,
  cache: Record<string, number>,
): number {
  if (spanId in cache) return cache[spanId];
  const parentId = parentMap[spanId];
  const depth =
    parentId && parentId in parentMap ? getDepth(parentId, parentMap, cache) + 1 : 0;
  cache[spanId] = depth;
  return depth;
}

const STATUS_BORDER: Record<string, string> = {
  success: "border-green-400",
  error:   "border-red-400",
  timeout: "border-yellow-400",
};

const STATUS_DOT: Record<string, string> = {
  success: "bg-green-400",
  error:   "bg-red-500",
  timeout: "bg-yellow-400",
};

export function SpanTimeline({
  spans,
}: {
  spans: SpanResponse[];
  totalMs: number;
}) {
  if (spans.length === 0) return null;

  const parentMap: Record<string, string | null> = Object.fromEntries(
    spans.map((s) => [s.span_id, s.parent_span_id]),
  );
  const depthCache: Record<string, number> = {};

  return (
    <div className="divide-y divide-gray-100">
      {spans.map((span, idx) => {
        const depth = getDepth(span.span_id, parentMap, depthCache);
        const isChild = depth > 0;
        const borderCls = STATUS_BORDER[span.status] ?? "border-gray-300";
        const dotCls = STATUS_DOT[span.status] ?? "bg-gray-400";

        return (
          <div
            key={span.span_id}
            className={`flex items-start gap-3 py-3 ${isChild ? "bg-gray-50/60" : ""}`}
            style={{ paddingLeft: 20 + depth * 24 }}
          >
            {/* Step number */}
            <span className="text-xs text-gray-300 font-mono w-5 shrink-0 pt-0.5 text-right">
              {idx + 1}
            </span>

            {/* Status bar + content */}
            <div className={`flex-1 border-l-2 pl-3 ${borderCls}`}>
              <div className="flex items-center gap-2 flex-wrap">
                {/* Status dot */}
                <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${dotCls}`} />

                {/* Action (primary) */}
                <span className="text-sm font-semibold text-gray-900">{span.action}</span>

                {/* Agent name */}
                <span className="text-xs text-gray-400">{span.agent_name}</span>

                {/* Model pill */}
                {span.model && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 font-mono">
                    {span.model}
                  </span>
                )}
              </div>

              {/* Metrics row */}
              <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                <span>{formatDuration(span.duration_ms)}</span>

                {(span.input_tokens > 0 || span.output_tokens > 0) && (
                  <span>
                    {span.input_tokens.toLocaleString()} in /{" "}
                    {span.output_tokens.toLocaleString()} out tokens
                  </span>
                )}

                {span.cost_usd > 0 && (
                  <span className="font-mono">{formatCost(span.cost_usd)}</span>
                )}
              </div>

              {/* Error message */}
              {span.error_msg && (
                <p className="mt-1 text-xs text-red-600 bg-red-50 rounded px-2 py-1">
                  {span.error_msg}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

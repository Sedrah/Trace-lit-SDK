/**
 * Gantt-style span timeline.
 * Each row = one span, width proportional to duration.
 * Root spans (no parent) anchored at left; child spans offset by their start time.
 */

import type { SpanResponse } from "../types";
import { StatusBadge, formatCost, formatDuration } from "./ui";

function getDepth(spanId: string, parentMap: Record<string, string | null>, cache: Record<string, number>): number {
  if (spanId in cache) return cache[spanId];
  const parentId = parentMap[spanId];
  const depth = parentId && parentId in parentMap ? getDepth(parentId, parentMap, cache) + 1 : 0;
  cache[spanId] = depth;
  return depth;
}

export function SpanTimeline({
  spans,
  totalMs,
}: {
  spans: SpanResponse[];
  totalMs: number;
}) {
  if (spans.length === 0 || totalMs === 0) return null;

  const traceStart = Math.min(...spans.map((s) => new Date(s.timestamp).getTime()));
  const effectiveTotal = Math.max(totalMs, 1);

  const parentMap: Record<string, string | null> = Object.fromEntries(
    spans.map((s) => [s.span_id, s.parent_span_id])
  );
  const depthCache: Record<string, number> = {};

  return (
    <div className="space-y-1.5">
      {spans.map((span) => {
        const startMs = new Date(span.timestamp).getTime() - traceStart;
        const widthPct = Math.max((span.duration_ms / effectiveTotal) * 100, 0.5);
        const offsetPct = (startMs / effectiveTotal) * 100;
        const depth = getDepth(span.span_id, parentMap, depthCache);
        const isChild = depth > 0;

        return (
          <div key={span.span_id} className="flex items-center gap-3 text-xs">
            {/* Label column — indented for child spans */}
            <div
              className="w-52 shrink-0 flex items-center gap-1.5 overflow-hidden"
              style={{ paddingLeft: depth * 16 }}
            >
              <StatusBadge status={span.status} />
              <div className="overflow-hidden">
                <p className="truncate font-medium text-gray-800" title={span.action}>
                  {span.action}
                </p>
                <p className="truncate text-gray-400" title={span.agent_name}>
                  {isChild ? (span.model ?? span.agent_name) : span.agent_name}
                </p>
              </div>
            </div>

            {/* Bar track */}
            <div className="flex-1 h-5 bg-gray-100 rounded relative overflow-hidden">
              <div
                className={`absolute top-0 h-full rounded ${
                  span.status === "error"
                    ? "bg-red-400"
                    : span.status === "timeout"
                    ? "bg-yellow-400"
                    : isChild
                    ? "bg-brand-300"
                    : "bg-brand-500"
                }`}
                style={{ left: `${offsetPct}%`, width: `${widthPct}%`, minWidth: 4 }}
              />
            </div>

            {/* Duration + cost */}
            <div className="w-28 shrink-0 flex items-center gap-2 justify-end text-gray-500">
              <span>{formatDuration(span.duration_ms)}</span>
              {span.cost_usd > 0 && (
                <span className="font-mono text-gray-400">{formatCost(span.cost_usd)}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

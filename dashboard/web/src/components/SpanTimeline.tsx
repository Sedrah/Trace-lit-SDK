/**
 * Gantt-style span timeline.
 * Each row = one span, width proportional to duration.
 * Root spans (no parent) anchored at left; child spans offset by their start time.
 */

import type { SpanResponse } from "../types";
import { StatusBadge, formatCost, formatDuration } from "./ui";

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

  return (
    <div className="space-y-1.5">
      {spans.map((span) => {
        const startMs = new Date(span.timestamp).getTime() - traceStart;
        const widthPct = Math.max((span.duration_ms / effectiveTotal) * 100, 0.5);
        const offsetPct = (startMs / effectiveTotal) * 100;

        return (
          <div key={span.span_id} className="flex items-center gap-3 text-xs">
            {/* Label column */}
            <div className="w-48 shrink-0 flex items-center gap-1.5 overflow-hidden">
              <StatusBadge status={span.status} />
              <span className="truncate text-gray-700 font-medium" title={`${span.agent_name} — ${span.action}`}>
                {span.agent_name}
              </span>
            </div>

            {/* Bar track */}
            <div className="flex-1 h-6 bg-gray-100 rounded relative overflow-hidden">
              <div
                className={`absolute top-0 h-full rounded transition-all ${
                  span.status === "error"
                    ? "bg-red-400"
                    : span.status === "timeout"
                    ? "bg-yellow-400"
                    : "bg-brand-400"
                }`}
                style={{
                  left: `${offsetPct}%`,
                  width: `${widthPct}%`,
                  minWidth: 4,
                }}
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

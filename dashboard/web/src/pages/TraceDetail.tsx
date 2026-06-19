import { useParams, useNavigate } from "react-router-dom";
import { useAttribution, useDag, useTrace } from "../api/hooks";
import {
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  StatusBadge,
  formatCost,
  formatDuration,
} from "../components/ui";
import { DAGView } from "../components/DAGView";
import { SpanTimeline } from "../components/SpanTimeline";
import { format } from "date-fns";
import type { AttributionResponse } from "../types";

function AttributionPanel({ data }: { data: AttributionResponse }) {
  if (!data.has_failures) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
        <span className="text-base">⚡</span>
        <h2 className="text-sm font-semibold text-gray-700">Failure Attribution</h2>
        <span className="text-xs text-gray-400 ml-1">— what went wrong and why</span>
      </div>
      <div className="p-5 space-y-4">
        {data.root_causes.map((rc) => (
          <div key={rc.span_id} className="rounded-md bg-red-50 border border-red-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700">
                Root cause
              </span>
              <span className="text-sm font-semibold text-gray-800">
                {rc.agent_name} — {rc.action}
              </span>
            </div>
            <p className="text-sm text-red-700">{rc.description}</p>
            {rc.summary && rc.summary !== rc.description && (
              <div className="mt-3 pt-3 border-t border-red-200">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-xs font-medium text-gray-500">AI analysis</span>
                  <span className="inline-flex px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700">✦ Enterprise</span>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">{rc.summary}</p>
              </div>
            )}
            {rc.cascaded_to.length > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                Cascaded to {rc.cascaded_to.length} downstream{" "}
                {rc.cascaded_to.length === 1 ? "step" : "steps"}
              </p>
            )}
          </div>
        ))}

        {data.cascades.length > 0 && (
          <div className="space-y-2">
            {data.cascades.map((c) => (
              <div key={c.span_id} className="rounded-md bg-orange-50 border border-orange-200 px-4 py-3 flex items-start gap-3">
                <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-700 shrink-0 mt-0.5">
                  Cascade
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    {c.agent_name} — {c.action}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Failed because {c.caused_by_agent} — {c.caused_by_action} failed first
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TraceDetail() {
  const { traceId = "" } = useParams();
  const navigate = useNavigate();

  const { data: trace, isLoading: traceLoading, isError: traceError } = useTrace(traceId);
  const { data: dag,   isLoading: dagLoading } = useDag(traceId);
  const { data: attribution } = useAttribution(traceId, (trace?.error_spans ?? 0) > 0);

  if (traceLoading) return <LoadingSpinner message="Loading trace…" />;
  if (traceError || !trace) return <ErrorMessage message="Trace not found." />;

  return (
    <div>
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-gray-200 bg-white">
        <button
          onClick={() => navigate(-1)}
          className="text-xs text-brand-600 hover:underline mb-2 block"
        >
          ← Back to Traces
        </button>
        <div className="flex items-center gap-3">
          <StatusBadge status={trace.status} />
          <FrameworkBadge framework={trace.framework} />
          <h1 className="text-xl font-semibold text-gray-900">{trace.agent_name}</h1>
        </div>
        <p className="text-xs text-gray-400 mt-1 font-mono">{traceId}</p>

        {/* Summary row */}
        <div className="flex items-center gap-6 mt-4 text-sm text-gray-600">
          <span>
            <span className="text-gray-400">Started </span>
            {format(new Date(trace.started_at), "MMM d, yyyy HH:mm:ss")}
          </span>
          <span>
            <span className="text-gray-400">Duration </span>
            {formatDuration(trace.total_duration_ms)}
          </span>
          <span>
            <span className="text-gray-400">Spans </span>
            {trace.total_spans}
            {trace.error_spans > 0 && (
              <span className="text-red-500 ml-1">({trace.error_spans} failed)</span>
            )}
          </span>
          <span>
            <span className="text-gray-400">Cost </span>
            <span className="font-mono font-medium">{formatCost(trace.total_cost_usd)}</span>
          </span>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Attribution panel — only shown for failed traces */}
        {attribution && attribution.has_failures && (
          <AttributionPanel data={attribution} />
        )}

        {/* DAG */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-5 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Execution Graph</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Each box is a step. Green = success, red = error.
              {attribution?.has_failures && " ⚡ = root cause, ↩ = cascade."}
            </p>
          </div>
          <div className="h-80">
            {dagLoading ? (
              <LoadingSpinner message="Building graph…" />
            ) : dag ? (
              <DAGView dag={dag} attribution={attribution} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Graph unavailable
              </div>
            )}
          </div>
        </div>

        {/* Span timeline */}
        {trace.spans && trace.spans.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200">
            <div className="px-5 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-700">Steps</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Every step in order — duration, tokens, and cost where available.
              </p>
            </div>
            <div className="p-5">
              <SpanTimeline spans={trace.spans} totalMs={trace.total_duration_ms} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

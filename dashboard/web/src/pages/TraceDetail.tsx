import { useParams, useNavigate } from "react-router-dom";
import { useDag, useTrace } from "../api/hooks";
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

export default function TraceDetail() {
  const { traceId = "" } = useParams();
  const navigate = useNavigate();

  const { data: trace, isLoading: traceLoading, isError: traceError } = useTrace(traceId);
  const { data: dag,   isLoading: dagLoading } = useDag(traceId);

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
        {/* DAG */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-5 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Execution Graph</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Each box is a step. Green = success, red = error. Hover for details.
            </p>
          </div>
          <div className="h-80">
            {dagLoading ? (
              <LoadingSpinner message="Building graph…" />
            ) : dag ? (
              <DAGView dag={dag} />
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
              <h2 className="text-sm font-semibold text-gray-700">Step Timeline</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Each row is one step. Width = time spent. Cost shown where available.
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

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTraces } from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  PageHeader,
  StatusBadge,
  Table,
  Td,
  Th,
  formatCost,
  formatDuration,
} from "../components/ui";
import { format } from "date-fns";

export default function Traces() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [agentFilter, setAgentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isError } = useTraces({
    page,
    page_size: 50,
    agent_name: agentFilter || undefined,
    status: statusFilter || undefined,
  });

  return (
    <div>
      <PageHeader
        title="Traces"
        subtitle="Every agent run — click a row for details and the execution graph"
      />

      {/* Filters */}
      <div className="px-6 py-3 bg-white border-b border-gray-200 flex items-center gap-3">
        <input
          type="text"
          placeholder="Filter by agent name…"
          value={agentFilter}
          onChange={(e) => { setAgentFilter(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-md px-3 py-1.5 text-sm w-56 focus:outline-none focus:ring-1 focus:ring-brand-400"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-400"
        >
          <option value="">All statuses</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>
        {data && (
          <span className="text-xs text-gray-400 ml-auto">
            {data.meta.total.toLocaleString()} total
          </span>
        )}
      </div>

      <div className="p-6">
        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <ErrorMessage message="Could not load traces. Is the API running?" />
        ) : (data?.items.length ?? 0) === 0 ? (
          <EmptyState message="No agent runs found." />
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <Table>
              <thead>
                <tr>
                  <Th>Status</Th>
                  <Th>Agent</Th>
                  <Th>Framework</Th>
                  <Th>Started</Th>
                  <Th>Duration</Th>
                  <Th>Spans</Th>
                  <Th>Cost</Th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((t) => (
                  <tr
                    key={t.trace_id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/traces/${t.trace_id}`)}
                  >
                    <Td><StatusBadge status={t.status} /></Td>
                    <Td className="font-medium text-gray-900">{t.agent_name}</Td>
                    <Td><FrameworkBadge framework={t.framework} /></Td>
                    <Td className="text-gray-400 text-xs whitespace-nowrap">
                      {format(new Date(t.started_at), "MMM d, HH:mm:ss")}
                    </Td>
                    <Td>{formatDuration(t.total_duration_ms)}</Td>
                    <Td>
                      <span className={t.error_spans > 0 ? "text-red-600 font-medium" : ""}>
                        {t.total_spans}
                        {t.error_spans > 0 && ` (${t.error_spans} failed)`}
                      </span>
                    </Td>
                    <Td className="font-mono text-xs">{formatCost(t.total_cost_usd)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            {/* Pagination */}
            {(data!.meta.total > 50) && (
              <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
                <span>Page {page}</span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                  >
                    ← Previous
                  </button>
                  <button
                    disabled={!data!.meta.has_more}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

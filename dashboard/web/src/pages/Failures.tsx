import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFailures } from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  PageHeader,
  Table,
  Td,
  Th,
  formatDuration,
} from "../components/ui";
import { format, subHours } from "date-fns";

const CATEGORY_COLOURS: Record<string, string> = {
  "LLM Timeout":            "bg-yellow-100 text-yellow-800",
  "Rate Limit Exceeded":    "bg-orange-100 text-orange-800",
  "Context Length Exceeded":"bg-purple-100 text-purple-800",
  "Tool Call Failed":       "bg-red-100   text-red-800",
  "Tool Returned Empty":    "bg-gray-100  text-gray-600",
  "Agent Loop Detected":    "bg-pink-100  text-pink-800",
  "Authentication Error":   "bg-red-100   text-red-800",
  "Network Error":          "bg-blue-100  text-blue-800",
  "Invalid Response":       "bg-indigo-100 text-indigo-800",
  "Agent Code Error":       "bg-red-100   text-red-800",
  "Unknown Error":          "bg-gray-100  text-gray-600",
};

const since = subHours(new Date(), 24).toISOString();
const until = new Date().toISOString();

export default function Failures() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [agentFilter, setAgentFilter] = useState("");

  const { data, isLoading, isError } = useFailures({
    page,
    page_size: 50,
    agent_name: agentFilter || undefined,
    since,
    until,
  });

  return (
    <div>
      <PageHeader
        title="Failures"
        subtitle="Every error classified in plain English — click a row to see the full trace"
      />

      <div className="px-6 py-3 bg-white border-b border-gray-200 flex items-center gap-3">
        <input
          type="text"
          placeholder="Filter by agent…"
          value={agentFilter}
          onChange={(e) => { setAgentFilter(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-md px-3 py-1.5 text-sm w-56 focus:outline-none focus:ring-1 focus:ring-brand-400"
        />
        {data && (
          <span className="text-xs text-gray-400 ml-auto">
            {data.meta.total.toLocaleString()} failures
          </span>
        )}
      </div>

      <div className="p-6">
        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <ErrorMessage message="Could not load failures." />
        ) : (data?.items.length ?? 0) === 0 ? (
          <EmptyState message="No failures in the last 24 hours. 🎉" />
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>Agent</Th>
                  <Th>Action</Th>
                  <Th>Framework</Th>
                  <Th>What happened</Th>
                  <Th>Duration</Th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((f) => (
                  <tr
                    key={f.span_id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/traces/${f.trace_id}`)}
                  >
                    <Td className="text-xs text-gray-400 whitespace-nowrap">
                      {format(new Date(f.timestamp), "MMM d, HH:mm:ss")}
                    </Td>
                    <Td className="font-medium text-gray-900">{f.agent_name}</Td>
                    <Td className="text-gray-500">{f.action}</Td>
                    <Td><FrameworkBadge framework={f.framework} /></Td>
                    <Td>
                      <div>
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                            CATEGORY_COLOURS[f.classification] ?? "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {f.classification}
                        </span>
                        <p className="text-xs text-gray-500 mt-1 max-w-sm line-clamp-2">
                          {f.description}
                        </p>
                      </div>
                    </Td>
                    <Td>{formatDuration(f.duration_ms)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            {data!.meta.total > 50 && (
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

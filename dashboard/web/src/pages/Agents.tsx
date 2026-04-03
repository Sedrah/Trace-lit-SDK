import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAgentMetrics, useAgents } from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  PageHeader,
  Table,
  Td,
  Th,
  formatCost,
  formatDuration,
} from "../components/ui";
import { format, subHours } from "date-fns";

const since = subHours(new Date(), 24).toISOString();
const until = new Date().toISOString();

function AgentMetricsPanel({ agentName }: { agentName: string }) {
  const [metric, setMetric] = useState("cost_usd");
  const { data, isLoading } = useAgentMetrics(agentName, {
    metric_name: metric,
    granularity: "hourly",
    since,
    until,
  });

  const chartData = (data?.points ?? []).map((p) => ({
    time: format(new Date(p.bucket), "HH:mm"),
    value: Number(p.total.toFixed(6)),
  }));

  return (
    <div className="mt-4 bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">{agentName} — Hourly trend</h3>
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none"
        >
          <option value="cost_usd">Cost (USD)</option>
          <option value="duration_ms">Duration (ms)</option>
          <option value="call_count">Call count</option>
          <option value="error_count">Error count</option>
        </select>
      </div>
      {isLoading ? (
        <LoadingSpinner />
      ) : chartData.length === 0 ? (
        <EmptyState message="No metric data for this period." />
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#4f6ef7" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function Agents() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const { data, isLoading, isError } = useAgents({ since, until });

  return (
    <div>
      <PageHeader
        title="Agents"
        subtitle="Performance summary for each agent in the last 24 hours"
      />
      <div className="p-6">
        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <ErrorMessage message="Could not load agent data." />
        ) : (data?.items.length ?? 0) === 0 ? (
          <EmptyState message="No agents have run yet." />
        ) : (
          <>
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <Table>
                <thead>
                  <tr>
                    <Th>Agent</Th>
                    <Th>Framework</Th>
                    <Th>Runs</Th>
                    <Th>Error rate</Th>
                    <Th>Avg duration</Th>
                    <Th>Total cost</Th>
                    <Th>Last seen</Th>
                  </tr>
                </thead>
                <tbody>
                  {data!.items.map((a) => (
                    <tr
                      key={a.agent_name}
                      className={`cursor-pointer hover:bg-gray-50 ${
                        selectedAgent === a.agent_name ? "bg-brand-50" : ""
                      }`}
                      onClick={() =>
                        setSelectedAgent(
                          selectedAgent === a.agent_name ? null : a.agent_name,
                        )
                      }
                    >
                      <Td className="font-medium text-gray-900">{a.agent_name}</Td>
                      <Td><FrameworkBadge framework={a.framework} /></Td>
                      <Td>{a.call_count.toLocaleString()}</Td>
                      <Td>
                        <span className={a.error_rate > 0.1 ? "text-red-600 font-medium" : "text-green-600"}>
                          {(a.error_rate * 100).toFixed(1)}%
                        </span>
                      </Td>
                      <Td>{formatDuration(a.avg_duration_ms)}</Td>
                      <Td className="font-mono text-xs">{formatCost(a.total_cost_usd)}</Td>
                      <Td className="text-gray-400 text-xs">
                        {format(new Date(a.last_seen), "MMM d, HH:mm")}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>

            {selectedAgent && (
              <AgentMetricsPanel agentName={selectedAgent} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

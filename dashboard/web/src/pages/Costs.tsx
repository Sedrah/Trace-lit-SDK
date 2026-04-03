import { useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useCosts } from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  PageHeader,
  StatCard,
  Table,
  Td,
  Th,
  formatCost,
} from "../components/ui";
import { subDays, subHours } from "date-fns";

const PALETTE = ["#4f6ef7","#7c3aed","#0891b2","#059669","#d97706","#dc2626","#64748b","#ec4899"];

const PERIODS = [
  { label: "Last 24 hours", since: () => subHours(new Date(), 24).toISOString() },
  { label: "Last 7 days",   since: () => subDays(new Date(), 7).toISOString() },
  { label: "Last 30 days",  since: () => subDays(new Date(), 30).toISOString() },
];

export default function Costs() {
  const [periodIdx, setPeriodIdx] = useState(0);
  const since = PERIODS[periodIdx].since();
  const until = new Date().toISOString();

  const { data, isLoading, isError } = useCosts({ since, until });

  const pieData = (data?.breakdown ?? []).slice(0, 8).map((item, i) => ({
    name: item.agent_name,
    value: Number(item.total_cost_usd.toFixed(6)),
    color: PALETTE[i % PALETTE.length],
  }));

  return (
    <div>
      <PageHeader
        title="Costs"
        subtitle="USD spend across all agents"
        actions={
          <div className="flex gap-1">
            {PERIODS.map((p, i) => (
              <button
                key={p.label}
                onClick={() => setPeriodIdx(i)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  i === periodIdx
                    ? "bg-brand-500 text-white"
                    : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        }
      />

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard
            label="Total spend"
            value={formatCost(data?.total_cost_usd ?? 0)}
            sub={PERIODS[periodIdx].label.toLowerCase()}
            accent="blue"
          />
          <StatCard
            label="Agents spending"
            value={String(data?.breakdown.length ?? 0)}
            sub="distinct agents"
          />
          <StatCard
            label="Avg per agent"
            value={
              data && data.breakdown.length > 0
                ? formatCost(data.total_cost_usd / data.breakdown.length)
                : "$0.00"
            }
            sub="mean cost"
          />
        </div>

        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <ErrorMessage message="Could not load cost data." />
        ) : (data?.breakdown.length ?? 0) === 0 ? (
          <EmptyState message="No cost data for this period." />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Pie chart */}
            <div className="bg-white rounded-lg border border-gray-200 p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Share by agent</h2>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, percent }) =>
                      `${name} ${(percent * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCost(v)} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <Table>
                <thead>
                  <tr>
                    <Th>Agent</Th>
                    <Th>Framework</Th>
                    <Th>Runs</Th>
                    <Th>Total cost</Th>
                    <Th>Avg / run</Th>
                  </tr>
                </thead>
                <tbody>
                  {data!.breakdown.map((item) => (
                    <tr key={item.agent_name} className="hover:bg-gray-50">
                      <Td className="font-medium text-gray-900">{item.agent_name}</Td>
                      <Td><FrameworkBadge framework={item.framework} /></Td>
                      <Td>{item.call_count.toLocaleString()}</Td>
                      <Td className="font-mono text-xs font-medium">
                        {formatCost(item.total_cost_usd)}
                      </Td>
                      <Td className="font-mono text-xs text-gray-400">
                        {formatCost(item.avg_cost_per_call)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

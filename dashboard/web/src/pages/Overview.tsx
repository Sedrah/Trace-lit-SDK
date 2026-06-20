import { subHours } from "date-fns";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCosts, useFailures, useTraces } from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  FrameworkBadge,
  LoadingSpinner,
  PageHeader,
  StatCard,
  StatusBadge,
  formatCost,
  formatDuration,
} from "../components/ui";
import { useNavigate } from "react-router-dom";

const now = new Date();
const since24h = subHours(now, 24).toISOString();
const until = now.toISOString();

export default function Overview() {
  const navigate = useNavigate();

  const traces = useTraces({ since: since24h, until, page_size: 5 });
  const costs  = useCosts({ since: since24h, until });
  const failures = useFailures({ since: since24h, until, page_size: 5 });

  const totalCost    = costs.data?.total_cost_usd ?? 0;
  const traceCount   = traces.data?.meta.total ?? 0;
  const errorCount   = failures.data?.meta.total ?? 0;
  const errorRate    = traceCount > 0 ? ((errorCount / traceCount) * 100).toFixed(1) : "0.0";

  // Cost breakdown for bar chart
  const chartData = (costs.data?.breakdown ?? []).slice(0, 8).map((item) => ({
    name: item.agent_name,
    cost: Number(item.total_cost_usd.toFixed(4)),
  }));

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Last 24 hours across all agents"
      />

      <div className="p-6 space-y-6">
        {/* Getting started banner — shown only when there are no traces yet */}
        {!traces.isLoading && traceCount === 0 && (
          <div className="rounded-lg border border-brand-200 bg-brand-50 p-5">
            <p className="text-sm font-semibold text-brand-800 mb-3">
              Welcome — send your first trace in 3 steps
            </p>
            <ol className="space-y-2 text-sm text-brand-700">
              <li>
                <span className="font-medium">1. Install the SDK</span>
                <code className="ml-2 text-xs bg-white border border-brand-200 rounded px-1.5 py-0.5 font-mono">
                  pip install tracelit-sdk
                </code>
              </li>
              <li>
                <span className="font-medium">2. Create an API key</span>
                {" — "}
                <a href="/settings" className="underline hover:text-brand-900">
                  Settings → Create key
                </a>
              </li>
              <li>
                <span className="font-medium">3. Instrument your agent</span>
                <code className="ml-2 text-xs bg-white border border-brand-200 rounded px-1.5 py-0.5 font-mono">
                  @trace_lit.trace(agent_name="my-agent")
                </code>
              </li>
            </ol>
            <a
              href="https://github.com/Sedrah/Trace-lit-SDK#quickstart"
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-block text-xs text-brand-600 underline hover:text-brand-800"
            >
              Full quickstart guide →
            </a>
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Cost"
            value={formatCost(totalCost)}
            sub="last 24 hours"
            accent="blue"
          />
          <StatCard
            label="Agent Runs"
            value={traceCount.toLocaleString()}
            sub="traces recorded"
            accent="gray"
          />
          <StatCard
            label="Failures"
            value={errorCount.toLocaleString()}
            sub={`${errorRate}% error rate`}
            accent={errorCount > 0 ? "red" : "green"}
          />
          <StatCard
            label="Active Agents"
            value={String(costs.data?.breakdown.length ?? 0)}
            sub="distinct agents"
            accent="gray"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Cost by agent bar chart */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Cost by Agent (USD)
            </h2>
            {costs.isLoading ? (
              <LoadingSpinner />
            ) : costs.isError ? (
              <ErrorMessage message="Could not load cost data." />
            ) : chartData.length === 0 ? (
              <EmptyState message="No cost data yet." />
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(180, chartData.length * 36)}>
                <BarChart
                  layout="vertical"
                  data={chartData}
                  margin={{ left: 8, right: 24, top: 4, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `$${v}`}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    width={140}
                    tickFormatter={(name: string) =>
                      name.length > 18 ? name.slice(0, 17) + "…" : name
                    }
                  />
                  <Tooltip formatter={(v: number) => [formatCost(v), "Cost"]} />
                  <Bar dataKey="cost" fill="#4f6ef7" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Recent failures */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Recent Failures
            </h2>
            {failures.isLoading ? (
              <LoadingSpinner />
            ) : failures.isError ? (
              <ErrorMessage message="Could not load failures." />
            ) : (failures.data?.items.length ?? 0) === 0 ? (
              <EmptyState message="No failures in the last 24 hours. 🎉" />
            ) : (
              <ul className="divide-y divide-gray-100">
                {failures.data!.items.map((f) => (
                  <li
                    key={f.span_id}
                    className="py-2.5 cursor-pointer hover:bg-gray-50 -mx-2 px-2 rounded"
                    onClick={() => navigate(`/traces/${f.trace_id}`)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-gray-800 truncate">
                        {f.agent_name}
                      </span>
                      <span className="text-xs text-red-600 font-medium shrink-0">
                        {f.classification}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                      {f.description}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Recent traces */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Recent Runs</h2>
            <button
              onClick={() => navigate("/traces")}
              className="text-xs text-brand-600 hover:underline"
            >
              View all →
            </button>
          </div>
          {traces.isLoading ? (
            <LoadingSpinner />
          ) : traces.isError ? (
            <ErrorMessage message="Could not load traces." />
          ) : (traces.data?.items.length ?? 0) === 0 ? (
            <EmptyState message="No agent runs yet." />
          ) : (
            <ul className="divide-y divide-gray-100">
              {traces.data!.items.map((t) => (
                <li
                  key={t.trace_id}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/traces/${t.trace_id}`)}
                >
                  <StatusBadge status={t.status} />
                  <FrameworkBadge framework={t.framework} />
                  <span className="flex-1 text-sm font-medium text-gray-800 truncate">
                    {t.agent_name}
                  </span>
                  <span className="text-xs text-gray-400">
                    {formatDuration(t.total_duration_ms)}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">
                    {formatCost(t.total_cost_usd)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

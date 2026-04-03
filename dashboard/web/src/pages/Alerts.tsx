import { useState } from "react";
import { useAlerts, useCreateAlert, useDeleteAlert } from "../api/hooks";
import type { AlertRuleRequest } from "../types";
import {
  Button,
  EmptyState,
  ErrorMessage,
  LoadingSpinner,
  PageHeader,
  Table,
  Td,
  Th,
} from "../components/ui";
import { format } from "date-fns";

function NewAlertForm({ onDone }: { onDone: () => void }) {
  const create = useCreateAlert();
  const [form, setForm] = useState<AlertRuleRequest>({
    name: "",
    agent_name: "",
    metric: "cost_usd",
    threshold: 1.0,
    window_minutes: 60,
    channel: "slack",
    webhook_url: "",
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(
      { ...form, agent_name: form.agent_name || null },
      { onSuccess: onDone },
    );
  }

  const label = (text: string) => (
    <label className="block text-xs font-medium text-gray-600 mb-1">{text}</label>
  );
  const input = (
    key: keyof AlertRuleRequest,
    extra?: React.InputHTMLAttributes<HTMLInputElement>,
  ) => (
    <input
      {...extra}
      value={String(form[key] ?? "")}
      onChange={(e) =>
        setForm((f) => ({
          ...f,
          [key]: extra?.type === "number" ? Number(e.target.value) : e.target.value,
        }))
      }
      className="border border-gray-200 rounded-md px-3 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-brand-400"
    />
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg border border-gray-200 p-5 space-y-4"
    >
      <h3 className="text-sm font-semibold text-gray-700">New alert rule</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          {label("Rule name")}
          {input("name", { required: true, placeholder: "High cost spike" })}
        </div>
        <div>
          {label("Agent name (leave blank for all agents)")}
          {input("agent_name", { placeholder: "research-agent" })}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          {label("Metric")}
          <select
            value={form.metric}
            onChange={(e) => setForm((f) => ({ ...f, metric: e.target.value }))}
            className="border border-gray-200 rounded-md px-3 py-1.5 text-sm w-full"
          >
            <option value="cost_usd">Cost (USD)</option>
            <option value="error_rate">Error rate</option>
            <option value="duration_ms">Duration (ms)</option>
          </select>
        </div>
        <div>
          {label("Threshold")}
          {input("threshold", { type: "number", step: "0.01", required: true })}
        </div>
        <div>
          {label("Window (minutes)")}
          {input("window_minutes", { type: "number", min: "1", required: true })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          {label("Notify via")}
          <select
            value={form.channel}
            onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}
            className="border border-gray-200 rounded-md px-3 py-1.5 text-sm w-full"
          >
            <option value="slack">Slack webhook</option>
            <option value="webhook">HTTP webhook</option>
          </select>
        </div>
        <div>
          {label("Webhook URL")}
          {input("webhook_url", {
            required: true,
            placeholder: "https://hooks.slack.com/services/…",
          })}
        </div>
      </div>

      {create.isError && (
        <p className="text-xs text-red-600">
          {(create.error as Error).message}
        </p>
      )}

      <div className="flex gap-2 justify-end">
        <Button variant="secondary" onClick={onDone}>Cancel</Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Create alert"}
        </Button>
      </div>
    </form>
  );
}

export default function Alerts() {
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading, isError } = useAlerts();
  const deleteAlert = useDeleteAlert();

  return (
    <div>
      <PageHeader
        title="Alerts"
        subtitle="Get notified when an agent costs too much, fails too often, or runs too slowly"
        actions={
          !showForm && (
            <Button onClick={() => setShowForm(true)}>+ New alert</Button>
          )
        }
      />

      <div className="p-6 space-y-4">
        {showForm && <NewAlertForm onDone={() => setShowForm(false)} />}

        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <ErrorMessage message="Could not load alert rules." />
        ) : (data?.items.length ?? 0) === 0 && !showForm ? (
          <EmptyState message="No alert rules yet. Create one to get notified when things go wrong." />
        ) : (data?.items.length ?? 0) > 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Agent</Th>
                  <Th>Condition</Th>
                  <Th>Channel</Th>
                  <Th>Created</Th>
                  <Th>{" "}</Th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <Td className="font-medium text-gray-900">{r.name}</Td>
                    <Td className="text-gray-500">{r.agent_name ?? "All agents"}</Td>
                    <Td>
                      <span className="text-xs">
                        {r.metric} &gt; {r.threshold} over {r.window_minutes}m
                      </span>
                    </Td>
                    <Td>
                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                        {r.channel}
                      </span>
                    </Td>
                    <Td className="text-xs text-gray-400">
                      {format(new Date(r.created_at), "MMM d, yyyy")}
                    </Td>
                    <Td>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => deleteAlert.mutate(r.id)}
                        disabled={deleteAlert.isPending}
                      >
                        Remove
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ) : null}
      </div>
    </div>
  );
}

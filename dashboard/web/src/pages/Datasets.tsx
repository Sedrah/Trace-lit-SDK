import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
  getDatasets,
  createDataset,
  deleteDataset,
  getDatasetItems,
  deleteDatasetItem,
  downloadDatasetExport,
  runEval,
  getEvalRuns,
} from "../api/client";
import type { DatasetResponse, DatasetItemResponse, EvalRunResponse } from "../types";

const LABEL_STYLES: Record<string, string> = {
  good:    "bg-green-100 text-green-700",
  bad:     "bg-red-100 text-red-600",
  neutral: "bg-gray-100 text-gray-500",
};

// ---------------------------------------------------------------------------
// Dataset list (left panel)
// ---------------------------------------------------------------------------

function DatasetList({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["datasets"], queryFn: getDatasets });

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createDataset(name.trim(), desc.trim() || undefined),
    onSuccess: (ds) => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      setCreating(false);
      setName("");
      setDesc("");
      onSelect(ds.id);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["datasets"] }),
  });

  return (
    <div className="flex flex-col h-full border-r border-gray-200">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800">Datasets</h2>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="text-xs px-2 py-1 bg-brand-600 text-white rounded hover:bg-brand-700"
          >
            + New
          </button>
        )}
      </div>

      {creating && (
        <div className="p-3 border-b border-gray-100 space-y-2">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Dataset name"
            className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <input
            type="text"
            value={desc}
            onChange={e => setDesc(e.target.value)}
            placeholder="Description (optional)"
            className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate()}
              disabled={!name.trim() || createMutation.isPending}
              className="flex-1 text-xs py-1.5 bg-brand-600 text-white rounded hover:bg-brand-700 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating…" : "Create"}
            </button>
            <button onClick={() => setCreating(false)} className="text-xs text-gray-400 hover:text-gray-600">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <p className="px-4 py-3 text-sm text-gray-400">Loading…</p>
        ) : !data?.items.length ? (
          <p className="px-4 py-6 text-sm text-gray-400 text-center">No datasets yet.</p>
        ) : (
          data.items.map((ds: DatasetResponse) => (
            <button
              key={ds.id}
              onClick={() => onSelect(ds.id)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 group ${
                selected === ds.id ? "bg-brand-50 border-l-2 border-l-brand-500" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900 truncate">{ds.name}</span>
                <button
                  onClick={e => {
                    e.stopPropagation();
                    if (confirm(`Delete dataset "${ds.name}"? This cannot be undone.`)) {
                      deleteMutation.mutate(ds.id);
                      if (selected === ds.id) onSelect("");
                    }
                  }}
                  className="text-xs text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 shrink-0 ml-2"
                >
                  Delete
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                {ds.item_count} {ds.item_count === 1 ? "example" : "examples"}
              </p>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dataset items (right panel)
// ---------------------------------------------------------------------------

function DatasetItems({ datasetId }: { datasetId: string }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["dataset-items", datasetId],
    queryFn: () => getDatasetItems(datasetId),
  });

  const deleteMutation = useMutation({
    mutationFn: (itemId: string) => deleteDatasetItem(datasetId, itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dataset-items", datasetId] }),
  });

  async function handleExport() {
    if (!data) return;
    setDownloading(true);
    try {
      await downloadDatasetExport(datasetId, `${data.dataset.name.replace(/\s+/g, "_")}.jsonl`);
    } finally {
      setDownloading(false);
    }
  }

  if (isLoading) return <div className="p-6 text-sm text-gray-400">Loading…</div>;
  if (!data) return null;

  const { dataset, items } = data;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{dataset.name}</h2>
          {dataset.description && (
            <p className="text-xs text-gray-400 mt-0.5">{dataset.description}</p>
          )}
        </div>
        <button
          onClick={handleExport}
          disabled={downloading || items.length === 0}
          className="text-xs px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1.5"
        >
          {downloading ? "Downloading…" : "↓ Export JSONL"}
        </button>
      </div>

      {/* Items */}
      {items.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
          <div className="text-center">
            <p>No examples yet.</p>
            <p className="text-xs mt-1 text-gray-300">
              Open a trace, expand a step, and click "Add to dataset".
            </p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b border-gray-200 text-xs text-gray-400 uppercase tracking-wide">
                <th className="px-4 py-2 text-left">Label</th>
                <th className="px-4 py-2 text-left">Step</th>
                <th className="px-4 py-2 text-left">Agent</th>
                <th className="px-4 py-2 text-left">Model</th>
                <th className="px-4 py-2 text-left">Notes</th>
                <th className="px-4 py-2 text-left">Added</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((item: DatasetItemResponse) => {
                const hasIO = !!(item.input_text || item.output_text);
                const isExpanded = expanded === item.id;
                return (
                  <>
                    <tr
                      key={item.id}
                      onClick={() => hasIO && setExpanded(isExpanded ? null : item.id)}
                      className={`border-b border-gray-50 hover:bg-gray-50 ${hasIO ? "cursor-pointer" : ""}`}
                    >
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${LABEL_STYLES[item.label] ?? ""}`}>
                          {item.label}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-gray-900">
                        {item.action ?? "—"}
                        {hasIO && <span className="ml-1 text-gray-400 text-xs">{isExpanded ? "▴" : "▾"}</span>}
                      </td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs">{item.agent_name ?? "—"}</td>
                      <td className="px-4 py-2.5">
                        {item.model ? (
                          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">
                            {item.model}
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 max-w-xs truncate">
                        {item.notes ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-400">
                        {format(new Date(item.created_at), "MMM d")}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            deleteMutation.mutate(item.id);
                          }}
                          className="text-xs text-red-400 hover:text-red-600"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${item.id}-io`} className="bg-gray-50 border-b border-gray-200">
                        <td />
                        <td colSpan={6} className="px-4 py-3 space-y-3">
                          {item.input_text && (
                            <div>
                              <p className="text-xs font-semibold text-gray-500 mb-1">Input</p>
                              <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words max-h-40">
                                {item.input_text}
                              </pre>
                            </div>
                          )}
                          {item.output_text && (
                            <div>
                              <p className="text-xs font-semibold text-gray-500 mb-1">Output</p>
                              <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words max-h-40">
                                {item.output_text}
                              </pre>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Eval panel
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-600",
  error:  "bg-gray-100 text-gray-500",
};

function EvalPanel({ datasetId }: { datasetId: string }) {
  const qc = useQueryClient();
  const [promptName, setPromptName]       = useState("");
  const [promptVersion, setPromptVersion] = useState("");
  const [baselineVersion, setBaselineVersion] = useState("");
  const [threshold, setThreshold]         = useState("0.8");
  const [lastResult, setLastResult]       = useState<EvalRunResponse | null>(null);

  const { data: runsData } = useQuery({
    queryKey: ["eval-runs", datasetId],
    queryFn: () => getEvalRuns(datasetId),
  });

  const runMutation = useMutation({
    mutationFn: () => runEval(datasetId, {
      prompt_name: promptName.trim(),
      prompt_version: parseInt(promptVersion, 10),
      baseline_version: baselineVersion ? parseInt(baselineVersion, 10) : undefined,
      threshold: parseFloat(threshold) || 0.8,
    }),
    onSuccess: (result) => {
      setLastResult(result);
      qc.invalidateQueries({ queryKey: ["eval-runs", datasetId] });
    },
  });

  const canRun = promptName.trim() && promptVersion && !runMutation.isPending;

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800">Quality gate</h2>
        <p className="text-xs text-gray-400 mt-0.5">
          Score a prompt version against this dataset's labeled examples.
        </p>
      </div>

      {/* Run form */}
      <div className="p-5 border-b border-gray-100 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Prompt name</label>
            <input
              type="text"
              value={promptName}
              onChange={e => setPromptName(e.target.value)}
              placeholder="e.g. system-prompt"
              className="w-full text-sm px-2.5 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">New version #</label>
            <input
              type="number"
              value={promptVersion}
              onChange={e => setPromptVersion(e.target.value)}
              placeholder="e.g. 3"
              className="w-full text-sm px-2.5 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Baseline version # <span className="text-gray-300 font-normal">(leave blank = use dataset)</span>
            </label>
            <input
              type="number"
              value={baselineVersion}
              onChange={e => setBaselineVersion(e.target.value)}
              placeholder="optional"
              className="w-full text-sm px-2.5 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Pass threshold</label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={threshold}
              onChange={e => setThreshold(e.target.value)}
              className="w-full text-sm px-2.5 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>

        <button
          onClick={() => runMutation.mutate()}
          disabled={!canRun}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded hover:bg-brand-700 disabled:opacity-50"
        >
          {runMutation.isPending ? "Running…" : "Run eval"}
        </button>

        {/* Inline result */}
        {lastResult && (
          <div className={`rounded-lg border p-4 ${lastResult.status === "passed" ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-bold ${STATUS_STYLES[lastResult.status]}`}>
                {lastResult.status.toUpperCase()}
              </span>
              <span className="text-sm font-semibold text-gray-800">
                Score {(lastResult.score * 100).toFixed(0)}% (threshold {(lastResult.threshold * 100).toFixed(0)}%)
              </span>
            </div>
            <p className="text-xs text-gray-600">{lastResult.message}</p>
          </div>
        )}

        {runMutation.isError && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            Eval failed — check that the prompt name and version exist in traces.
          </p>
        )}
      </div>

      {/* CI snippet */}
      <div className="px-5 py-4 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-600 mb-2">Use in CI (GitHub Actions)</p>
        <pre className="text-xs bg-gray-900 text-green-400 rounded p-3 overflow-x-auto whitespace-pre">{`- name: Quality gate
  run: |
    curl -sf -X POST \\
      https://app.trace-lit.com/api/v1/datasets/${datasetId}/eval \\
      -H "X-Tracelit-Api-Key: \${{ secrets.TRACELIT_API_KEY }}" \\
      -H "Content-Type: application/json" \\
      -d '{"prompt_name":"${promptName || "your-prompt"}","prompt_version":\$VERSION,"threshold":${threshold}}'`}</pre>
      </div>

      {/* Run history */}
      <div className="flex-1 overflow-y-auto">
        <p className="px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-100">
          Run history
        </p>
        {!runsData?.items.length ? (
          <p className="px-5 py-4 text-sm text-gray-400">No eval runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase tracking-wide">
                <th className="px-4 py-2 text-left">Result</th>
                <th className="px-4 py-2 text-left">Prompt</th>
                <th className="px-4 py-2 text-right">Score</th>
                <th className="px-4 py-2 text-right">Spans</th>
                <th className="px-4 py-2 text-left">When</th>
              </tr>
            </thead>
            <tbody>
              {runsData.items.map((run: EvalRunResponse) => (
                <tr key={run.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[run.status]}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-700">
                    {run.prompt_name} <span className="text-gray-400">v{run.prompt_version}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs font-mono text-gray-700">
                    {(run.score * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs text-gray-400">
                    {run.new_spans} new / {run.baseline_spans} base
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-400">
                    {format(new Date(run.created_at), "MMM d HH:mm")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type Tab = "examples" | "eval";

export default function Datasets() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab]               = useState<Tab>("examples");

  return (
    <div className="flex h-[calc(100vh-56px)]">
      <div className="w-64 shrink-0">
        <DatasetList selected={selectedId} onSelect={(id) => { setSelectedId(id); setTab("examples"); }} />
      </div>
      <div className="flex-1 overflow-hidden flex flex-col">
        {selectedId ? (
          <>
            {/* Tab bar */}
            <div className="flex border-b border-gray-200 bg-white shrink-0">
              {(["examples", "eval"] as Tab[]).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-5 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    tab === t
                      ? "border-brand-600 text-brand-700"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t === "examples" ? "Examples" : "Quality gate"}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-hidden">
              {tab === "examples"
                ? <DatasetItems datasetId={selectedId} />
                : <EvalPanel datasetId={selectedId} />}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-gray-400">
            Select a dataset or create a new one.
          </div>
        )}
      </div>
    </div>
  );
}

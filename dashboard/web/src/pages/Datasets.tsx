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
} from "../api/client";
import type { DatasetResponse, DatasetItemResponse } from "../types";

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
// Page
// ---------------------------------------------------------------------------

export default function Datasets() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="flex h-[calc(100vh-56px)]">
      <div className="w-64 shrink-0">
        <DatasetList selected={selectedId} onSelect={setSelectedId} />
      </div>
      <div className="flex-1 overflow-hidden">
        {selectedId ? (
          <DatasetItems datasetId={selectedId} />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-gray-400">
            Select a dataset or create a new one.
          </div>
        )}
      </div>
    </div>
  );
}

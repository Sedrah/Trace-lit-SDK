import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
  listSettingsKeys,
  createSettingsKey,
  deleteSettingsKey,
  getSessionToken,
  type SettingsKeyResponse,
  type CreateSettingsKeyResponse,
} from "../api/client";

// ---------------------------------------------------------------------------
// SDK Keys section
// ---------------------------------------------------------------------------

function CopyBox({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-md px-3 py-2 mt-3">
      <code className="flex-1 text-xs font-mono text-green-800 break-all">{value}</code>
      <button onClick={copy} className="shrink-0 text-xs font-medium text-green-700 hover:text-green-900">
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}

function SdkKeys() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["settings-keys"],
    queryFn: listSettingsKeys,
  });

  const [newKey, setNewKey] = useState<CreateSettingsKeyResponse | null>(null);
  const [creating, setCreating] = useState(false);
  const [keyName, setKeyName] = useState("SDK key");

  const createMutation = useMutation({
    mutationFn: () => createSettingsKey(keyName || "SDK key"),
    onSuccess: (result) => {
      setNewKey(result);
      setCreating(false);
      setKeyName("SDK key");
      qc.invalidateQueries({ queryKey: ["settings-keys"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSettingsKey,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings-keys"] }),
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">SDK API Keys</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Use in <code className="font-mono">TRACELIT_API_KEY=</code> when instrumenting agents.
          </p>
        </div>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="text-xs px-3 py-1.5 bg-brand-600 text-white rounded-md hover:bg-brand-700 transition-colors"
          >
            + Create key
          </button>
        )}
      </div>

      {newKey && (
        <div className="mx-5 mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs font-medium text-amber-800 mb-1">
            Save this key — it won't be shown again
          </p>
          <CopyBox value={newKey.api_key} />
          <button
            onClick={() => setNewKey(null)}
            className="mt-3 text-xs text-amber-700 hover:underline"
          >
            I've saved it
          </button>
        </div>
      )}

      {creating && (
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <input
            type="text"
            value={keyName}
            onChange={e => setKeyName(e.target.value)}
            placeholder="e.g. production"
            className="flex-1 text-sm px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="text-xs px-3 py-1.5 bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating…" : "Create"}
          </button>
          <button onClick={() => setCreating(false)} className="text-xs text-gray-400 hover:text-gray-600">
            Cancel
          </button>
        </div>
      )}

      {isLoading ? (
        <p className="px-5 py-4 text-sm text-gray-400">Loading…</p>
      ) : !data?.items.length ? (
        <p className="px-5 py-6 text-sm text-gray-400 text-center">
          No SDK keys yet. Create one to start sending traces.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase tracking-wide">
              <th className="px-5 py-2 text-left">Name</th>
              <th className="px-5 py-2 text-left">Created</th>
              <th className="px-5 py-2 text-right" />
            </tr>
          </thead>
          <tbody>
            {data.items.map((k: SettingsKeyResponse) => (
              <tr key={k.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-5 py-3 font-medium text-gray-800">{k.name}</td>
                <td className="px-5 py-3 text-gray-400 text-xs">
                  {format(new Date(k.created_at), "MMM d, yyyy")}
                </td>
                <td className="px-5 py-3 text-right">
                  <button
                    onClick={() => {
                      if (confirm("Revoke this key? Agents using it will stop sending traces.")) {
                        deleteMutation.mutate(k.id);
                      }
                    }}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Account section
// ---------------------------------------------------------------------------

function Account() {
  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => {
      const res = await fetch("/api/v1/auth/me", {
        headers: { "X-Tracelit-Session": getSessionToken() },
      });
      if (!res.ok) return null;
      return res.json() as Promise<{ org_id: string; email: string }>;
    },
    staleTime: Infinity,
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-4">Account</h2>
      <div className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-gray-500">Email</span>
          <span className="font-medium text-gray-800">{me?.email ?? "—"}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-500">Organisation</span>
          <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-700">
            {me?.org_id ?? "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Settings() {
  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Manage your account and SDK access.</p>
      </div>
      <Account />
      <SdkKeys />
    </div>
  );
}

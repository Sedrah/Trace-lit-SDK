import { useState } from "react";
import { format } from "date-fns";
import {
  clearApiKey,
  getStoredAdminKey,
  saveAdminKey,
  clearAdminKey,
  saveApiKey,
  getApiKey,
} from "../api/client";
import { useAdminKeys, useCreateAdminKey, useDeleteAdminKey } from "../api/hooks";
import type { ApiKeyCreateRequest, ApiKeyCreateResponse } from "../types";
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
import { ApiError } from "../api/client";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function maskKey(key: string): string {
  if (key.length <= 8) return "•".repeat(key.length);
  return key.slice(0, 6) + "•".repeat(8) + key.slice(-4);
}

function CopyBox({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(value).catch(() => {
      const el = document.createElement("textarea");
      el.value = value;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    });
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-md px-3 py-2">
      <span className="flex-1 text-sm font-mono text-green-800 break-all">{value}</span>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 text-xs font-medium text-green-700 hover:text-green-900 transition-colors"
      >
        {copied ? "Copied!" : `Copy ${label}`}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 1 — Org API key (what callers send as X-Tracelit-Api-Key)
// ---------------------------------------------------------------------------

function ApiKeyCard() {
  const current = getApiKey();
  const [input, setInput] = useState("");
  const [saved, setSaved] = useState(false);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    saveApiKey(input.trim());
    setInput("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    window.location.reload(); // re-init queries with new key
  }

  function handleClear() {
    clearApiKey();
    window.location.reload();
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-gray-800">Your API key</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Sent with every dashboard request to identify your organisation.
        </p>
      </div>

      {current ? (
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded px-3 py-1.5 flex-1">
            {maskKey(current)}
          </span>
          <Button variant="danger" size="sm" onClick={handleClear}>
            Clear key
          </Button>
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic">No API key set — all requests are keyless.</p>
      )}

      <form onSubmit={handleSave} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="sk-…"
          className="flex-1 border border-gray-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-400"
        />
        <Button type="submit" size="sm" disabled={!input.trim()}>
          {saved ? "Saved!" : "Save key"}
        </Button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 2 — Admin key management
// ---------------------------------------------------------------------------

function NewKeyForm({
  adminKey,
  onCreated,
  onCancel,
}: {
  adminKey: string;
  onCreated: (result: ApiKeyCreateResponse) => void;
  onCancel: () => void;
}) {
  const create = useCreateAdminKey(adminKey);
  const [form, setForm] = useState<ApiKeyCreateRequest>({
    org_id: "",
    name: "",
    expires_at: null,
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(
      { ...form, expires_at: form.expires_at || null },
      { onSuccess: onCreated },
    );
  }

  const field = (label: string, child: React.ReactNode) => (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {child}
    </div>
  );

  const inputCls =
    "border border-gray-200 rounded-md px-3 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-brand-400";

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg border border-gray-200 p-5 space-y-4"
    >
      <h3 className="text-sm font-semibold text-gray-700">Create new API key</h3>

      <div className="grid grid-cols-3 gap-4">
        {field(
          "Organisation ID",
          <input
            required
            value={form.org_id}
            onChange={(e) => setForm((f) => ({ ...f, org_id: e.target.value }))}
            placeholder="acme"
            className={inputCls}
          />,
        )}
        {field(
          "Key name",
          <input
            required
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="production"
            className={inputCls}
          />,
        )}
        {field(
          "Expires at (optional)",
          <input
            type="datetime-local"
            value={form.expires_at ?? ""}
            onChange={(e) =>
              setForm((f) => ({ ...f, expires_at: e.target.value || null }))
            }
            className={inputCls}
          />,
        )}
      </div>

      {create.isError && (
        <p className="text-xs text-red-600">{(create.error as Error).message}</p>
      )}

      <div className="flex gap-2 justify-end">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create key"}
        </Button>
      </div>
    </form>
  );
}

function KeyCreatedBanner({
  result,
  onDismiss,
}: {
  result: ApiKeyCreateResponse;
  onDismiss: () => void;
}) {
  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-5 space-y-3">
      <div>
        <p className="text-sm font-semibold text-green-800">
          Key created — copy it now
        </p>
        <p className="text-xs text-green-600 mt-0.5">
          This key will not be shown again. Store it somewhere safe.
        </p>
      </div>
      <CopyBox value={result.raw_key} label="key" />
      <div className="text-xs text-gray-500 space-y-0.5">
        <p>Org: <strong>{result.org_id}</strong></p>
        <p>Name: <strong>{result.name}</strong></p>
      </div>
      <Button size="sm" onClick={onDismiss}>
        Done, I've saved the key
      </Button>
    </div>
  );
}

function AdminKeyManagement({ adminKey }: { adminKey: string }) {
  const { data, isLoading, isError, error } = useAdminKeys(adminKey);
  const deleteKey = useDeleteAdminKey(adminKey);
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreateResponse | null>(null);

  const isUnauthorized =
    isError && error instanceof ApiError && error.status === 401;

  if (isLoading) return <LoadingSpinner />;

  if (isUnauthorized) {
    return (
      <ErrorMessage message="Invalid admin key. Clear it below and try again." />
    );
  }

  if (isError) {
    const msg = error instanceof ApiError && error.status === 503
      ? "Admin API is disabled on this instance."
      : "Could not load API keys.";
    return <ErrorMessage message={msg} />;
  }

  return (
    <div className="space-y-4">
      {created ? (
        <KeyCreatedBanner result={created} onDismiss={() => setCreated(null)} />
      ) : showForm ? (
        <NewKeyForm
          adminKey={adminKey}
          onCreated={(r) => { setCreated(r); setShowForm(false); }}
          onCancel={() => setShowForm(false)}
        />
      ) : null}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <p className="text-sm font-medium text-gray-700">API keys</p>
          {!showForm && !created && (
            <Button size="sm" onClick={() => setShowForm(true)}>
              + New key
            </Button>
          )}
        </div>

        {(data?.items.length ?? 0) === 0 ? (
          <EmptyState message="No API keys yet." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Organisation</Th>
                <Th>Created</Th>
                <Th>Expires</Th>
                <Th>{" "}</Th>
              </tr>
            </thead>
            <tbody>
              {data!.items.map((k) => (
                <tr key={k.id} className="hover:bg-gray-50">
                  <Td className="font-medium text-gray-900">{k.name}</Td>
                  <Td>
                    <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-brand-50 text-brand-700">
                      {k.org_id}
                    </span>
                  </Td>
                  <Td className="text-xs text-gray-400">
                    {format(new Date(k.created_at), "MMM d, yyyy")}
                  </Td>
                  <Td className="text-xs text-gray-400">
                    {k.expires_at
                      ? format(new Date(k.expires_at), "MMM d, yyyy")
                      : "Never"}
                  </Td>
                  <Td>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => deleteKey.mutate(k.id)}
                      disabled={deleteKey.isPending}
                    >
                      Revoke
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
    </div>
  );
}

function AdminSection() {
  const [adminKey, setAdminKey] = useState(getStoredAdminKey);
  const [input, setInput] = useState("");

  function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    saveAdminKey(trimmed);
    setAdminKey(trimmed);
    setInput("");
  }

  function handleLogout() {
    clearAdminKey();
    setAdminKey("");
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Key management</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Provision and revoke API keys for your organisations.
            Requires the admin key set in <code className="text-xs">TRACELIT_ADMIN_KEY</code>.
          </p>
        </div>
        {adminKey && (
          <Button variant="secondary" size="sm" onClick={handleLogout}>
            Sign out
          </Button>
        )}
      </div>

      {adminKey ? (
        <AdminKeyManagement adminKey={adminKey} />
      ) : (
        <form onSubmit={handleAuth} className="flex gap-2">
          <input
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter admin key"
            className="flex-1 border border-gray-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-400"
          />
          <Button type="submit" size="sm" disabled={!input.trim()}>
            Authenticate
          </Button>
        </form>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Settings() {
  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Manage your API key and provision keys for your organisation"
      />
      <div className="p-6 space-y-6 max-w-3xl">
        <ApiKeyCard />
        <AdminSection />
      </div>
    </div>
  );
}

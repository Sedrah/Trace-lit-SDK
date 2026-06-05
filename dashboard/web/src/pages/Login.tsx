import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { saveApiKey } from "../api/client";

export default function Login() {
  const [key, setKey]       = useState("");
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!key.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/v1/auth/me", {
        headers: { "X-Tracelit-Api-Key": key.trim() },
      });

      if (!res.ok) {
        setError("Invalid API key. Please check and try again.");
        return;
      }

      saveApiKey(key.trim());
      navigate("/", { replace: true });
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <span className="font-bold text-brand-600 text-2xl tracking-tight">Tracelit</span>
          <p className="text-sm text-gray-500 mt-1">Agent Monitoring & Observability</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          <h1 className="text-base font-semibold text-gray-900 mb-1">Sign in</h1>
          <p className="text-sm text-gray-500 mb-6">Enter your API key to access the dashboard.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                API Key
              </label>
              <input
                type="password"
                value={key}
                onChange={e => setKey(e.target.value)}
                placeholder="sk-…"
                autoFocus
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent font-mono"
              />
            </div>

            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !key.trim()}
              className="w-full py-2 px-4 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Verifying…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Contact your admin to get an API key.
        </p>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";

export default function Signup() {
  const [email, setEmail]   = useState("");
  const [sent, setSent]     = useState(false);
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/v1/auth/magic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? "Something went wrong. Please try again.");
        return;
      }

      setSent(true);
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <span className="font-bold text-brand-600 text-2xl tracking-tight">Tracelit</span>
          <p className="text-sm text-gray-500 mt-1">Agent Monitoring & Observability</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          {sent ? (
            <div className="text-center">
              <div className="text-3xl mb-3">📬</div>
              <h1 className="text-base font-semibold text-gray-900 mb-2">Check your email</h1>
              <p className="text-sm text-gray-500">
                We sent a verification link to <span className="font-medium text-gray-700">{email}</span>.
                Click it to get your API key.
              </p>
              <p className="text-xs text-gray-400 mt-4">Link expires in 24 hours.</p>
            </div>
          ) : (
            <>
              <h1 className="text-base font-semibold text-gray-900 mb-1">Create an account</h1>
              <p className="text-sm text-gray-500 mb-6">
                Enter your work email to get started.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">
                    Work email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    autoFocus
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                </div>

                {error && (
                  <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full py-2 px-4 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? "Sending…" : "Send verification link"}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-600 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

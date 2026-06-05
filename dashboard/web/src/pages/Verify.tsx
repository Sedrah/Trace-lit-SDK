import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { saveApiKey } from "../api/client";

type State = "loading" | "success" | "error";

export default function Verify() {
  const [params]  = useSearchParams();
  const navigate  = useNavigate();
  const [state, setState]   = useState<State>("loading");
  const [orgId, setOrgId]   = useState("");
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError]   = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("Missing verification token.");
      setState("error");
      return;
    }

    fetch(`/api/v1/auth/verify?token=${encodeURIComponent(token)}`)
      .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail ?? "Verification failed.");
        return data;
      })
      .then(data => {
        setOrgId(data.org_id);
        setApiKey(data.api_key);
        saveApiKey(data.api_key);
        setState("success");
      })
      .catch(err => {
        setError(err.message);
        setState("error");
      });
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function copyKey() {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (state === "loading") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-500">Verifying your email…</p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 shadow-sm p-8 text-center">
          <div className="text-3xl mb-3">❌</div>
          <h1 className="text-base font-semibold text-gray-900 mb-2">Verification failed</h1>
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => navigate("/signup")}
            className="mt-6 text-sm text-brand-600 hover:underline"
          >
            Try signing up again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <span className="font-bold text-brand-600 text-2xl tracking-tight">Tracelit</span>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          <div className="text-center mb-6">
            <div className="text-3xl mb-3">✅</div>
            <h1 className="text-base font-semibold text-gray-900 mb-1">Email verified</h1>
            <p className="text-sm text-gray-500">
              Your account is ready. You're signed in as{" "}
              <span className="font-medium text-gray-700">{orgId}</span>.
            </p>
          </div>

          {/* API key — shown once */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
            <p className="text-xs font-medium text-gray-500 mb-2">Your API key — save it now</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono text-gray-800 break-all">{apiKey}</code>
              <button
                onClick={copyKey}
                className="shrink-0 text-xs px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-6">
            This is the only time your API key will be shown. Copy it before continuing.
          </p>

          <button
            onClick={() => navigate("/")}
            className="w-full py-2 px-4 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 transition-colors"
          >
            Go to dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

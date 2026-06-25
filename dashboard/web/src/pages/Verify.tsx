import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { saveSessionToken } from "../api/client";

type State = "loading" | "success" | "error";

export default function Verify() {
  const [params]  = useSearchParams();
  const navigate  = useNavigate();
  const [state, setState] = useState<State>("loading");
  const [error, setError] = useState("");

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
        saveSessionToken(data.session_token);
        setState("success");
        // Short delay so the user sees the success state, then redirect
        const dest = localStorage.getItem("setup_complete") ? "/" : "/setup";
        setTimeout(() => navigate(dest, { replace: true }), 1500);
      })
      .catch(err => {
        setError(err.message);
        setState("error");
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 shadow-sm p-8 text-center">
        {state === "loading" && (
          <>
            <div className="text-3xl mb-3">⏳</div>
            <p className="text-sm text-gray-500">Signing you in…</p>
          </>
        )}

        {state === "success" && (
          <>
            <div className="text-3xl mb-3">✅</div>
            <h1 className="text-base font-semibold text-gray-900 mb-1">You're in</h1>
            <p className="text-sm text-gray-500">Taking you to the dashboard…</p>
          </>
        )}

        {state === "error" && (
          <>
            <div className="text-3xl mb-3">❌</div>
            <h1 className="text-base font-semibold text-gray-900 mb-2">Link invalid</h1>
            <p className="text-sm text-red-600 mb-4">{error}</p>
            <button
              onClick={() => navigate("/login")}
              className="text-sm text-brand-600 hover:underline"
            >
              Request a new link
            </button>
          </>
        )}
      </div>
    </div>
  );
}

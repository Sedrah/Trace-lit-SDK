import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  checkHasTraces,
  createSettingsKey,
  listSettingsKeys,
  type CreateSettingsKeyResponse,
} from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = "platform" | "provider" | "instructions" | "waiting" | "done";
type Platform =
  | "vercel" | "railway" | "render" | "flyio"
  | "n8n" | "flowise"
  | "python" | "other";
type Provider = "openai" | "anthropic" | "both" | "other";

// ---------------------------------------------------------------------------
// Platform / provider metadata
// ---------------------------------------------------------------------------

const PLATFORMS: { id: Platform; icon: string; name: string; desc: string }[] = [
  { id: "vercel",  icon: "▲", name: "Vercel",   desc: "Paste env vars in the Vercel dashboard" },
  { id: "railway", icon: "🚂", name: "Railway",  desc: "Add variables in the Railway service panel" },
  { id: "render",  icon: "🎯", name: "Render",   desc: "Set env vars in Render environment settings" },
  { id: "flyio",   icon: "🪁", name: "Fly.io",   desc: "Set secrets via the Fly.io dashboard or CLI" },
  { id: "n8n",     icon: "⚙️", name: "n8n",      desc: "Change your OpenAI credentials in n8n" },
  { id: "flowise", icon: "🌊", name: "Flowise",  desc: "Update the API base URL in your flow" },
  { id: "python",  icon: "🐍", name: "Python / local", desc: "Add two lines to your .env file" },
  { id: "other",   icon: "📦", name: "Other",    desc: "Works anywhere with env var support" },
];

const PROVIDERS: { id: Provider; name: string; label: string }[] = [
  { id: "openai",    name: "OpenAI",    label: "GPT-4o, GPT-4, GPT-3.5…" },
  { id: "anthropic", name: "Anthropic", label: "Claude Sonnet, Claude Haiku…" },
  { id: "both",      name: "Both",      label: "I use OpenAI and Anthropic" },
  { id: "other",     name: "Other / OTel", label: "LangChain, LangGraph, CrewAI, vLLM…" },
];

// ---------------------------------------------------------------------------
// Instruction content per platform
// ---------------------------------------------------------------------------

function proxyEnvVars(provider: Provider, key: string) {
  const tl = key || "<your-tracelit-key>";
  const vars: { name: string; value: string; note?: string }[] = [];

  if (provider === "openai" || provider === "both") {
    vars.push(
      { name: "OPENAI_BASE_URL", value: "https://app.trace-lit.com/proxy/openai/v1" },
      { name: "OPENAI_API_KEY",  value: `${tl}||<your-openai-key>`, note: "Replace <your-openai-key> with your real OpenAI key" },
    );
  }
  if (provider === "anthropic" || provider === "both") {
    vars.push(
      { name: "ANTHROPIC_BASE_URL", value: "https://app.trace-lit.com/proxy/anthropic/v1" },
      { name: "ANTHROPIC_API_KEY",  value: `${tl}||<your-anthropic-key>`, note: "Replace <your-anthropic-key> with your real Anthropic key" },
    );
  }
  if (provider === "other") {
    vars.push(
      { name: "OTEL_EXPORTER_OTLP_ENDPOINT", value: "https://app.trace-lit.com/otlp" },
      { name: "OTEL_EXPORTER_OTLP_HEADERS",  value: `Authorization=Bearer ${tl}` },
    );
  }
  return vars;
}

type InstructionStep = { title: string; body: string; screenshot?: string };

function getSteps(platform: Platform, provider: Provider): InstructionStep[] {
  const isProxy = provider !== "other";

  const uiSteps: Record<Platform, InstructionStep[]> = {
    vercel: [
      { title: "Open your Vercel project", body: "Go to vercel.com/dashboard → click your project." },
      { title: "Go to Settings → Environment Variables", body: "Click the Settings tab at the top, then Environment Variables in the left sidebar." },
      { title: "Add the env vars below", body: "Click Add New, paste each variable name and value, then click Save." },
      { title: "Redeploy", body: "Go to Deployments → click the three-dot menu on your latest deploy → Redeploy. Done!" },
    ],
    railway: [
      { title: "Open your Railway project", body: "Go to railway.app → open your project." },
      { title: "Click your service", body: "Click on the service that runs your AI agent." },
      { title: "Go to Variables tab", body: "Click the Variables tab. You'll see a list of env vars." },
      { title: "Add the env vars below", body: "Click New Variable, paste each name and value. Railway saves and restarts automatically." },
    ],
    render: [
      { title: "Open your Render service", body: "Go to dashboard.render.com → click your web service." },
      { title: "Go to Environment", body: "Click Environment in the left sidebar." },
      { title: "Add the env vars below", body: "Click Add Environment Variable for each one, paste the values, then click Save Changes." },
      { title: "Deploy", body: "Click Manual Deploy → Deploy latest commit. Your service will restart with the new settings." },
    ],
    flyio: [
      { title: "Open your Fly.io app dashboard", body: "Go to fly.io/dashboard and click your app, or use the Fly CLI." },
      { title: "Go to Secrets", body: "Click Secrets in the left sidebar. This is where env vars live." },
      { title: "Add each secret below", body: "Click New Secret, paste the name and value for each variable. Fly restarts automatically." },
    ],
    n8n: [
      { title: "Open n8n Credentials", body: "In n8n, click the Credentials icon in the left sidebar." },
      { title: "Find your OpenAI credentials", body: "Click on your existing OpenAI API credential to edit it." },
      { title: "Change the Base URL", body: "Find the 'Base URL' field and replace it with the value below." },
      { title: "Update the API Key", body: "Replace your current API key with the combined format below (your Trace-lit key + your OpenAI key joined by ||)." },
      { title: "Save and test", body: "Click Save. Run any workflow that uses OpenAI — it will now appear in your Trace-lit dashboard." },
    ],
    flowise: [
      { title: "Open your Flowise flow", body: "Open the flow that contains your AI agent in Flowise." },
      { title: "Click on your ChatOpenAI or LLM node", body: "Double-click the node to open its settings." },
      { title: "Click the credential gear icon", body: "Find the OpenAI API credential and click the pencil/edit icon." },
      { title: "Update Base URL and API Key", body: "Set the Base URL and API Key to the values below. Save the credential." },
      { title: "Run your flow", body: "Execute the flow. Within seconds, your run will appear in your Trace-lit dashboard." },
    ],
    python: [
      { title: "Open your .env file or terminal", body: "Find the .env file in your project root, or open a terminal where you run your agent." },
      { title: "Add or update the variables below", body: "Paste the env vars into your .env file, or export them in your terminal before running." },
      { title: "Restart your agent", body: "Re-run your agent script. Traces will appear in your dashboard within seconds." },
    ],
    other: [
      { title: "Find where your app reads environment variables", body: "This could be a .env file, a deployment platform settings page, a Docker run command, or a secrets manager." },
      { title: "Add the variables below", body: "Paste the variable names and values exactly as shown." },
      { title: "Restart your application", body: "After adding the variables, restart or redeploy your app. Traces will start flowing immediately." },
    ],
  };

  return uiSteps[platform] ?? uiSteps.other;
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

function CopyEnvVar({ name, value, note }: { name: string; value: string; note?: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden mb-3">
      <div className="bg-gray-50 px-3 py-1.5 border-b border-gray-200 flex items-center justify-between">
        <code className="text-xs font-mono font-semibold text-gray-700">{name}</code>
        <button
          onClick={copy}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <div className="px-3 py-2 bg-white flex items-center justify-between gap-2">
        <code className="text-xs font-mono text-gray-600 break-all">{value}</code>
      </div>
      {note && <div className="px-3 pb-2 text-xs text-amber-600">{note}</div>}
    </div>
  );
}

function ProgressDots({ current }: { current: number }) {
  const steps = ["Platform", "Provider", "Instructions", "Waiting", "Done"];
  return (
    <div className="flex items-center gap-3 justify-center mb-8">
      {steps.map((label, i) => (
        <div key={label} className="flex items-center gap-3">
          <div className="flex flex-col items-center gap-1">
            <div
              className={`w-2.5 h-2.5 rounded-full transition-all ${
                i < current
                  ? "bg-indigo-600"
                  : i === current
                  ? "bg-indigo-400 ring-4 ring-indigo-100"
                  : "bg-gray-200"
              }`}
            />
          </div>
          {i < steps.length - 1 && (
            <div className={`w-8 h-px ${i < current ? "bg-indigo-300" : "bg-gray-200"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

const STEP_INDEX: Record<Step, number> = {
  platform: 0,
  provider: 1,
  instructions: 2,
  waiting: 3,
  done: 4,
};

// ---------------------------------------------------------------------------
// Main wizard
// ---------------------------------------------------------------------------

export default function Setup() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("platform");
  const [platform, setPlatform] = useState<Platform | null>(null);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [tlKey, setTlKey] = useState("");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-create or load the first SDK key when entering instructions
  useEffect(() => {
    if (step !== "instructions") return;
    (async () => {
      try {
        const { items } = await listSettingsKeys();
        if (items.length > 0) {
          // Key values are masked after creation — show placeholder with instructions
          setTlKey("use-a-key-from-settings");
        } else {
          const created: CreateSettingsKeyResponse = await createSettingsKey("My first key");
          setTlKey(created.api_key);
        }
      } catch {
        setTlKey("<your-tracelit-key>");
      }
    })();
  }, [step]);

  // Poll for first trace on waiting screen
  useEffect(() => {
    if (step !== "waiting") return;
    pollingRef.current = setInterval(async () => {
      const has = await checkHasTraces();
      if (has) {
        clearInterval(pollingRef.current!);
        setStep("done");
      }
    }, 3000);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [step]);

  function finish() {
    localStorage.setItem("setup_complete", "1");
    navigate("/", { replace: true });
  }

  function skip() {
    localStorage.setItem("setup_complete", "1");
    navigate("/", { replace: true });
  }

  const envVars = platform && provider ? proxyEnvVars(provider, tlKey) : [];
  const instructionSteps = platform && provider ? getSteps(platform, provider) : [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 flex flex-col items-center justify-center px-4 py-12">
      {/* Skip button */}
      <div className="w-full max-w-2xl flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-indigo-400" />
          <span className="text-sm font-semibold text-gray-800">trace-lit</span>
        </div>
        <button onClick={skip} className="text-sm text-gray-400 hover:text-gray-600 transition-colors">
          Skip setup →
        </button>
      </div>

      <div className="w-full max-w-2xl bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-8 pt-8 pb-0">
          <ProgressDots current={STEP_INDEX[step]} />
        </div>

        {/* ── STEP 1: Platform ───────────────────────────────────────── */}
        {step === "platform" && (
          <div className="px-8 pb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Where is your AI agent running?</h1>
            <p className="text-gray-500 text-sm mb-6">
              Pick the platform your team uses to deploy or run the agent. We'll show you exactly where to click.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => { setPlatform(p.id); setStep("provider"); }}
                  className="flex items-start gap-3 p-4 rounded-xl border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all text-left group"
                >
                  <span className="text-xl mt-0.5">{p.icon}</span>
                  <div>
                    <div className="text-sm font-semibold text-gray-800 group-hover:text-indigo-700">{p.name}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{p.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── STEP 2: Provider ───────────────────────────────────────── */}
        {step === "provider" && (
          <div className="px-8 pb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Which AI provider does your agent use?</h1>
            <p className="text-gray-500 text-sm mb-6">
              This tells us which env vars to show you. You can always add more later.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => { setProvider(p.id); setStep("instructions"); }}
                  className="flex flex-col p-4 rounded-xl border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all text-left group"
                >
                  <div className="text-sm font-semibold text-gray-800 group-hover:text-indigo-700">{p.name}</div>
                  <div className="text-xs text-gray-400 mt-1">{p.label}</div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setStep("platform")}
              className="mt-5 text-sm text-gray-400 hover:text-gray-600"
            >
              ← Back
            </button>
          </div>
        )}

        {/* ── STEP 3: Instructions ───────────────────────────────────── */}
        {step === "instructions" && platform && provider && (
          <div className="px-8 pb-8">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{PLATFORMS.find(p => p.id === platform)?.icon}</span>
              <h1 className="text-2xl font-bold text-gray-900">
                {PLATFORMS.find(p => p.id === platform)?.name} setup
              </h1>
            </div>
            <p className="text-gray-500 text-sm mb-6">
              Follow these steps exactly. It takes about 3 minutes.
            </p>

            {/* Numbered steps */}
            <div className="space-y-4 mb-6">
              {instructionSteps.map((s, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-gray-800">{s.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{s.body}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Env vars to paste */}
            <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
              <p className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">
                {provider === "other" ? "OTel env vars to paste" : "Env vars to paste"}
              </p>

              {tlKey === "use-a-key-from-settings" ? (
                <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                  You already have a Trace-lit key. Go to{" "}
                  <a href="/settings" className="underline font-semibold">Settings → SDK Keys</a>{" "}
                  to copy it, then paste it in place of <code className="font-mono">&lt;your-tracelit-key&gt;</code> below.
                </div>
              ) : (
                <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800">
                  ✓ Your Trace-lit key is pre-filled below. Keep it safe — it won't be shown again.
                </div>
              )}

              {envVars.map((v) => (
                <CopyEnvVar key={v.name} name={v.name} value={v.value} note={v.note} />
              ))}
            </div>

            <div className="flex items-center justify-between mt-6">
              <button onClick={() => setStep("provider")} className="text-sm text-gray-400 hover:text-gray-600">
                ← Back
              </button>
              <button
                onClick={() => setStep("waiting")}
                className="px-6 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
              >
                I've pasted them — next →
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 4: Waiting ────────────────────────────────────────── */}
        {step === "waiting" && (
          <div className="px-8 pb-10 text-center">
            <div className="flex justify-center mb-6">
              <div className="relative w-16 h-16">
                <div className="absolute inset-0 rounded-full border-4 border-indigo-100" />
                <div className="absolute inset-0 rounded-full border-4 border-indigo-500 border-t-transparent animate-spin" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Waiting for your first trace…</h1>
            <p className="text-gray-500 text-sm max-w-sm mx-auto leading-relaxed">
              Run your agent now. As soon as it makes an AI call, it will appear here automatically.
            </p>
            <div className="mt-6 bg-gray-50 rounded-xl border border-gray-200 px-6 py-4 text-left max-w-sm mx-auto">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Checklist</p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="text-green-500">✓</span> Env vars added to platform
                </li>
                <li className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="text-green-500">✓</span> App restarted / redeployed
                </li>
                <li className="flex items-center gap-2 text-xs text-indigo-600 font-medium">
                  <span className="animate-pulse">●</span> Waiting for an AI call…
                </li>
              </ul>
            </div>
            <button onClick={skip} className="mt-6 text-sm text-gray-400 hover:text-gray-600">
              I'll come back later →
            </button>
          </div>
        )}

        {/* ── STEP 5: Done ───────────────────────────────────────────── */}
        {step === "done" && (
          <div className="px-8 pb-10 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
                <span className="text-3xl">🎉</span>
              </div>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Your first trace is here!</h1>
            <p className="text-gray-500 text-sm max-w-sm mx-auto leading-relaxed mb-6">
              Trace-lit is now connected. Every AI call your agent makes will appear in your dashboard in real time.
            </p>
            <button
              onClick={finish}
              className="px-8 py-3 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Go to my dashboard →
            </button>
          </div>
        )}
      </div>

      <p className="mt-6 text-xs text-gray-400">
        Need help?{" "}
        <a href="mailto:en.sedra@gmail.com" className="underline hover:text-gray-600">
          Email us
        </a>{" "}
        — we reply within a few hours.
      </p>
    </div>
  );
}

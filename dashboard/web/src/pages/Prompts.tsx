import { useEffect, useState } from "react";
import {
  usePromptVersion,
  usePromptVersionMetrics,
  usePromptVersions,
  usePrompts,
} from "../api/hooks";
import {
  EmptyState,
  ErrorMessage,
  LoadingSpinner,
  PageHeader,
  formatCost,
  formatDuration,
} from "../components/ui";
import { lineDiff } from "../utils/lineDiff";
import { format } from "date-fns";

export default function Prompts() {
  const { data, isLoading, isError } = usePrompts();
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedPrompt && data && data.items.length > 0) {
      setSelectedPrompt(data.items[0].prompt_name);
    }
  }, [data, selectedPrompt]);

  return (
    <div>
      <PageHeader
        title="Prompts"
        subtitle="Versions are detected automatically — no manual tagging required"
      />

      <div className="flex h-[calc(100vh-73px)]">
        <aside className="w-72 shrink-0 border-r border-gray-200 bg-white overflow-y-auto">
          {isLoading ? (
            <LoadingSpinner />
          ) : isError ? (
            <ErrorMessage message="Could not load prompts." />
          ) : (data?.items.length ?? 0) === 0 ? (
            <EmptyState message="No prompts traced yet. Call span.set_prompt(name, content) in your agent code." />
          ) : (
            <ul>
              {data!.items.map((p) => (
                <li key={p.prompt_name}>
                  <button
                    onClick={() => setSelectedPrompt(p.prompt_name)}
                    className={`w-full text-left px-4 py-3 border-b border-gray-100 transition-colors ${
                      selectedPrompt === p.prompt_name
                        ? "bg-brand-50"
                        : "hover:bg-gray-50"
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {p.prompt_name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {p.version_count} version{p.version_count === 1 ? "" : "s"} · latest v{p.latest_version}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto">
          {selectedPrompt ? (
            <PromptDetail promptName={selectedPrompt} />
          ) : (
            <EmptyState message="Select a prompt to see its version history." />
          )}
        </main>
      </div>
    </div>
  );
}

function PromptDetail({ promptName }: { promptName: string }) {
  const { data, isLoading, isError } = usePromptVersions(promptName);
  const [versionA, setVersionA] = useState<number | null>(null);
  const [versionB, setVersionB] = useState<number | null>(null);

  useEffect(() => {
    if (data && data.items.length > 0) {
      const versions = data.items.map((v) => v.version);
      setVersionA(Math.max(...versions));
      setVersionB(versions.length > 1 ? Math.max(...versions) - 1 : null);
    }
  }, [data]);

  if (isLoading) return <LoadingSpinner />;
  if (isError) return <ErrorMessage message="Could not load versions for this prompt." />;
  if (!data || data.items.length === 0) {
    return <EmptyState message="No versions found." />;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Version timeline</h2>
        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
          {[...data.items].reverse().map((v) => (
            <VersionRow
              key={v.version}
              promptName={promptName}
              version={v}
              isComparedA={versionA === v.version}
              isComparedB={versionB === v.version}
              onCompareA={() => setVersionA(v.version)}
              onCompareB={() => setVersionB(v.version)}
            />
          ))}
        </div>
      </div>

      {versionA !== null && versionB !== null && versionA !== versionB && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">
            Diff — v{versionB} → v{versionA}
          </h2>
          <DiffView promptName={promptName} versionA={versionA} versionB={versionB} />
        </div>
      )}
    </div>
  );
}

function VersionRow({
  promptName,
  version,
  isComparedA,
  isComparedB,
  onCompareA,
  onCompareB,
}: {
  promptName: string;
  version: { version: number; prompt_hash: string; first_seen_at: string; preview: string };
  isComparedA: boolean;
  isComparedB: boolean;
  onCompareA: () => void;
  onCompareB: () => void;
}) {
  const { data: metrics } = usePromptVersionMetrics(promptName, version.version);

  return (
    <div className="px-4 py-3 flex items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900">v{version.version}</span>
          <span className="font-mono text-xs text-gray-400">{version.prompt_hash}</span>
          <span className="text-xs text-gray-400">
            {format(new Date(version.first_seen_at), "MMM d, yyyy HH:mm")}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1 truncate font-mono">{version.preview}</p>
        {metrics && (
          <div className="flex gap-4 mt-2 text-xs text-gray-500">
            <span>{metrics.span_count.toLocaleString()} calls</span>
            <span>{formatCost(metrics.avg_cost_usd)} avg cost</span>
            <span>{formatDuration(metrics.avg_duration_ms)} avg duration</span>
            <span className={metrics.error_rate > 0 ? "text-red-600 font-medium" : ""}>
              {(metrics.error_rate * 100).toFixed(1)}% error rate
            </span>
          </div>
        )}
      </div>
      <div className="flex gap-1.5 shrink-0">
        <button
          onClick={onCompareA}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
            isComparedA
              ? "bg-brand-500 text-white"
              : "border border-gray-200 text-gray-500 hover:bg-gray-50"
          }`}
        >
          A
        </button>
        <button
          onClick={onCompareB}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
            isComparedB
              ? "bg-brand-500 text-white"
              : "border border-gray-200 text-gray-500 hover:bg-gray-50"
          }`}
        >
          B
        </button>
      </div>
    </div>
  );
}

function DiffView({
  promptName,
  versionA,
  versionB,
}: {
  promptName: string;
  versionA: number;
  versionB: number;
}) {
  const { data: contentA, isLoading: loadingA } = usePromptVersion(promptName, versionA);
  const { data: contentB, isLoading: loadingB } = usePromptVersion(promptName, versionB);

  if (loadingA || loadingB) return <LoadingSpinner />;
  if (!contentA || !contentB) return <ErrorMessage message="Could not load prompt content." />;

  const diff = lineDiff(contentB.content, contentA.content);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 font-mono text-xs overflow-x-auto">
      {diff.map((line, idx) => (
        <div
          key={idx}
          className={
            line.type === "added"
              ? "bg-green-50 text-green-800"
              : line.type === "removed"
              ? "bg-red-50 text-red-800"
              : "text-gray-600"
          }
        >
          <span className="select-none mr-2 text-gray-400">
            {line.type === "added" ? "+" : line.type === "removed" ? "-" : " "}
          </span>
          {line.text || " "}
        </div>
      ))}
    </div>
  );
}

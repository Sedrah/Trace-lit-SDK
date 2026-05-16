/**
 * DAG visualization using React Flow (@xyflow/react).
 *
 * Nodes are laid out top-to-bottom by span timestamp order.
 * Each node is labeled with agent_name + action (no raw IDs shown to users).
 * Colors: green = success, red = error, gray = root/unknown.
 */

import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AttributionResponse, DAGResponse } from "../types";
import { formatCost, formatDuration } from "./ui";

// ---------------------------------------------------------------------------
// Custom node
// ---------------------------------------------------------------------------

function SpanNode({ data }: NodeProps) {
  const d = data as {
    label: string;
    status: string;
    duration_ms: number;
    cost_usd: number;
    error_msg: string | null;
    attribution?: "root_cause" | "cascade" | null;
    attribution_label?: string | null;
  };

  const colours: Record<string, string> = {
    success: "border-green-400 bg-green-50",
    error:   "border-red-400   bg-red-50",
    timeout: "border-yellow-400 bg-yellow-50",
  };
  const attributionCls: Record<string, string> = {
    root_cause: "border-red-600 bg-red-50 ring-2 ring-red-400",
    cascade:    "border-orange-400 bg-orange-50",
  };
  const cls = d.attribution
    ? attributionCls[d.attribution]
    : (colours[d.status] ?? "border-gray-300 bg-white");

  return (
    <div
      className={`rounded-md border-2 px-3 py-2 min-w-[140px] max-w-[220px] shadow-sm ${cls}`}
      title={d.error_msg ?? d.label}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      {d.attribution && (
        <p className={`text-xs font-bold mb-1 ${d.attribution === "root_cause" ? "text-red-700" : "text-orange-600"}`}>
          {d.attribution === "root_cause" ? "⚡ Root cause" : "↩ Cascade"}
        </p>
      )}
      <p className="text-xs font-semibold text-gray-800 leading-tight truncate">{d.label}</p>
      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
        <span>{formatDuration(d.duration_ms)}</span>
        {d.cost_usd > 0 && <span className="font-mono">{formatCost(d.cost_usd)}</span>}
      </div>
      {d.attribution_label && (
        <p className="text-xs text-orange-700 mt-1 italic">{d.attribution_label}</p>
      )}
      {d.error_msg && !d.attribution_label && (
        <p className="text-xs text-red-600 mt-1 line-clamp-2">{d.error_msg}</p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  );
}

const nodeTypes = { spanNode: SpanNode };

// ---------------------------------------------------------------------------
// Layout helper — simple top-to-bottom tree layout
// ---------------------------------------------------------------------------

const X_SPACING = 260;
const Y_SPACING = 120;

function computeLayout(
  nodes: DAGResponse["nodes"],
  edges: DAGResponse["edges"],
): { id: string; x: number; y: number }[] {
  // Build children map
  const children: Record<string, string[]> = {};
  const hasParent = new Set<string>();
  for (const e of edges) {
    (children[e.source] ??= []).push(e.target);
    hasParent.add(e.target);
  }
  const roots = nodes.map((n) => n.id).filter((id) => !hasParent.has(id));

  const positions: { id: string; x: number; y: number }[] = [];

  function walk(id: string, depth: number, siblingIndex: number, siblingCount: number) {
    const xOffset = siblingCount > 1
      ? (siblingIndex - (siblingCount - 1) / 2) * X_SPACING
      : 0;
    positions.push({ id, x: xOffset, y: depth * Y_SPACING });
    const kids = children[id] ?? [];
    kids.forEach((kid, i) => walk(kid, depth + 1, i, kids.length));
  }

  roots.forEach((r, i) => walk(r, 0, i, roots.length));
  return positions;
}

// ---------------------------------------------------------------------------
// DAGView component
// ---------------------------------------------------------------------------

export function DAGView({
  dag,
  attribution,
}: {
  dag: DAGResponse;
  attribution?: AttributionResponse | null;
}) {
  const positions = computeLayout(dag.nodes, dag.edges);
  const posMap = Object.fromEntries(positions.map((p) => [p.id, p]));

  const rootCauseIds = new Set(attribution?.root_causes.map((r) => r.span_id) ?? []);
  const cascadeMap = Object.fromEntries(
    attribution?.cascades.map((c) => [
      c.span_id,
      `Caused by ${c.caused_by_agent} — ${c.caused_by_action}`,
    ]) ?? [],
  );
  const cascadeSpanIds = new Set(attribution?.cascades.map((c) => c.span_id) ?? []);
  const blastRadiusIds = new Set([
    ...rootCauseIds,
    ...cascadeSpanIds,
  ]);

  const rfNodes = dag.nodes.map((n) => ({
    id: n.id,
    type: "spanNode",
    position: { x: (posMap[n.id]?.x ?? 0) + 300, y: posMap[n.id]?.y ?? 0 },
    data: {
      label: n.label,
      status: n.status,
      duration_ms: n.duration_ms,
      cost_usd: n.cost_usd,
      error_msg: n.error_msg,
      attribution: rootCauseIds.has(n.id)
        ? "root_cause"
        : cascadeSpanIds.has(n.id)
        ? "cascade"
        : null,
      attribution_label: cascadeMap[n.id] ?? null,
    },
  }));

  const rfEdges = dag.edges.map((e) => {
    const isBlast = blastRadiusIds.has(e.source) && blastRadiusIds.has(e.target);
    const color = isBlast ? "#f97316" : "#94a3b8";
    return {
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: isBlast ? 2 : 1 },
      label: formatDuration(e.duration_ms),
      labelStyle: { fontSize: 10, fill: color },
    };
  });

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#f1f5f9" />
      <Controls showInteractive={false} />
      <MiniMap
        nodeColor={(n) => {
          const status = (n.data as { status: string }).status;
          return status === "error" ? "#fca5a5" : status === "success" ? "#86efac" : "#e2e8f0";
        }}
        maskColor="rgba(255,255,255,0.6)"
      />
    </ReactFlow>
  );
}

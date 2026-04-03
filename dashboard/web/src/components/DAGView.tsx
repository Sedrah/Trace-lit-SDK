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
import type { DAGResponse } from "../types";
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
  };

  const colours: Record<string, string> = {
    success: "border-green-400 bg-green-50",
    error:   "border-red-400   bg-red-50",
    timeout: "border-yellow-400 bg-yellow-50",
  };
  const cls = colours[d.status] ?? "border-gray-300 bg-white";

  return (
    <div
      className={`rounded-md border-2 px-3 py-2 min-w-[140px] max-w-[220px] shadow-sm ${cls}`}
      title={d.error_msg ?? d.label}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      <p className="text-xs font-semibold text-gray-800 leading-tight truncate">{d.label}</p>
      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
        <span>{formatDuration(d.duration_ms)}</span>
        {d.cost_usd > 0 && <span className="font-mono">{formatCost(d.cost_usd)}</span>}
      </div>
      {d.error_msg && (
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

export function DAGView({ dag }: { dag: DAGResponse }) {
  const positions = computeLayout(dag.nodes, dag.edges);
  const posMap = Object.fromEntries(positions.map((p) => [p.id, p]));

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
    },
  }));

  const rfEdges = dag.edges.map((e) => ({
    id: `${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
    style: { stroke: "#94a3b8" },
    label: formatDuration(e.duration_ms),
    labelStyle: { fontSize: 10, fill: "#94a3b8" },
  }));

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

/** Custom scenario node (§8.2, §8.5). Visual state mirrors backend truth only. */

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Possibility } from "../types";
import { usePieStore } from "../stores/analysisStore";

export interface PieNodeData extends Record<string, unknown> {
  possibility: Possibility;
  busy: boolean;
  unexplored: boolean;
  childCount: number;
  simSummary?: string;
}

const IMPACT_COLOR: Record<string, string> = {
  low: "#5eead4",
  moderate: "#38bdf8",
  high: "#fbbf24",
  critical: "#fb7185",
};

export default function PossibilityNode({ data, selected }: NodeProps) {
  const node = (data as unknown as PieNodeData).possibility;
  const busy = (data as unknown as PieNodeData).busy;
  const unexplored = (data as unknown as PieNodeData).unexplored;
  const childCount = (data as unknown as PieNodeData).childCount;
  const select = usePieStore((s) => s.select);

  const isRoot = node.depth === 0;
  const statusClass = isRoot
    ? "root"
    : unexplored || node.status === "unexplored"
      ? "unexplored"
      : node.status === "alternative"
        ? "alternative"
        : busy || node.status === "exploring"
          ? "exploring"
          : "validated";

  const prob = node.probability;
  const probLabel =
    prob.status === "quantified" && prob.estimate !== null
      ? `P ${Math.round(prob.estimate * 100)}%`
      : "P ?";

  return (
    <div
      className={`pie-node ${statusClass} ${selected ? "selected" : ""}`}
      onClick={() => select(node.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") select(node.id);
      }}
      aria-label={`Scenario: ${node.title}`}
    >
      <Handle type="target" position={Position.Left} className="pie-handle" />
      <div className="pie-node-top">
        <span className={`impact-dot impact-${node.impact.level}`} title={`Impact: ${node.impact.level}`} />
        <span className="depth-badge">d{node.depth}</span>
        {node.status === "alternative" && <span className="tag alt-tag">what-if</span>}
        {unexplored && <span className="tag unexp-tag">unexplored</span>}
        {busy && <span className="tag busy-tag">exploring…</span>}
      </div>
      <div className="pie-node-title">{node.title}</div>
      <div className="pie-node-meta">
        <span className={`prob-chip ${prob.status}`}>{probLabel}</span>
        <span className="horizon-chip">{formatHorizon(node)}</span>
        {childCount > 0 && <span className="child-chip">{childCount}↓</span>}
      </div>
      <Handle type="source" position={Position.Right} className="pie-handle" />
    </div>
  );
}

function formatHorizon(node: Possibility): string {
  const h = node.time_horizon;
  if (h.minimum == null && h.maximum == null) return "horizon ?";
  if (h.minimum === h.maximum) return `~${h.minimum} ${h.unit}`;
  return `${h.minimum ?? "?"}–${h.maximum ?? "?"} ${h.unit}`;
}

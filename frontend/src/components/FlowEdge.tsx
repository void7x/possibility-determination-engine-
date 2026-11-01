/**
 * Animated rainbow flow edge (§8.5).
 *
 * Behaviour contract: colour communicates *computation activity*, never
 * likelihood or accuracy. A light pulse travels only when the backend is
 * actively working on the destination branch or when the edge was just
 * reported by a real event.
 */

import { BaseEdge, getBezierPath, useReactFlow, type EdgeProps } from "@xyflow/react";
import { useEffect, useState } from "react";
import { usePieStore } from "../stores/analysisStore";

export default function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
}: EdgeProps) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: 0.28,
  });

  const freshEdges = usePieStore((s) => s.freshEdges);
  const busyNodes = usePieStore((s) => s.busyNodes);
  const edges = usePieStore((s) => s.edges);
  const markSettled = usePieStore((s) => s.markEdgeSettled);
  const { setEdges } = useReactFlow();

  const edgeRec = edges.find((e) => e.id === id);
  const targetBusy = edgeRec ? busyNodes.has(edgeRec.target) : false;
  const isFresh = freshEdges.has(id);
  const isAlternative = edgeRec?.relationship === "ALTERNATIVE_TO";

  // A fresh pulse "travels" once, then settles (unless target still busy).
  const [traveling, setTraveling] = useState(isFresh);
  useEffect(() => {
    if (isFresh) {
      setTraveling(true);
      const timer = setTimeout(() => {
        setTraveling(false);
        markSettled(id);
      }, 2200);
      return () => clearTimeout(timer);
    }
    setTraveling(false);
    return undefined;
  }, [isFresh, id, markSettled]);

  const active = traveling || targetBusy;
  const strokeClass = isAlternative
    ? "edge-alt"
    : active
      ? "edge-active"
      : "edge-settled";

  return (
    <g className={`pie-edge ${strokeClass}`}>
      <defs>
        <linearGradient id={`rainbow-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#7c3aed" />
          <stop offset="25%" stopColor="#3b82f6" />
          <stop offset="50%" stopColor="#06b6d4" />
          <stop offset="75%" stopColor="#22c55e" />
          <stop offset="100%" stopColor="#eab308" />
        </linearGradient>
      </defs>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: isAlternative ? "#818cf8" : active ? `url(#rainbow-${id})` : "#2c3550",
          strokeWidth: isAlternative ? 1.6 : active ? 2.6 : 1.5,
          strokeDasharray: isAlternative ? "6 5" : undefined,
          filter: active ? "drop-shadow(0 0 6px rgba(56,189,248,0.55))" : undefined,
          transition: "stroke 0.5s ease, stroke-width 0.4s ease",
        }}
      />
      {traveling && (
        <path
          d={path}
          fill="none"
          stroke={`url(#rainbow-${id})`}
          strokeWidth={3.4}
          strokeLinecap="round"
          className="edge-pulse"
          style={{ filter: "drop-shadow(0 0 8px rgba(125,211,252,0.9))" }}
        />
      )}
    </g>
  );
}

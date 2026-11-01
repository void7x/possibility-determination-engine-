/** Central exploration canvas (§8.2, §8.6): zoom/pan, minimap, lazy fit. */

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useRef } from "react";
import { usePieStore } from "../stores/analysisStore";
import PossibilityNode, { type PieNodeData } from "./PossibilityNode";
import FlowEdge from "./FlowEdge";
import { NODE_SIZE } from "../layout";

const nodeTypes = { possibility: PossibilityNode };
const edgeTypes = { pie: FlowEdge };

function CanvasInner() {
  const nodes = usePieStore((s) => s.nodes);
  const edges = usePieStore((s) => s.edges);
  const positions = usePieStore((s) => s.positions);
  const busyNodes = usePieStore((s) => s.busyNodes);
  const unexplored = usePieStore((s) => s.unexplored);
  const simulations = usePieStore((s) => s.simulations);
  const selectedId = usePieStore((s) => s.selectedId);
  const analysisStatus = usePieStore((s) => s.analysisStatus);
  const rf = useReactFlow();

  const rfNodes: Node[] = useMemo(() => {
    const childCounts: Record<string, number> = {};
    for (const node of Object.values(nodes)) {
      for (const parent of node.parent_ids) {
        childCounts[parent] = (childCounts[parent] ?? 0) + 1;
      }
    }
    return Object.values(nodes).map((node) => {
      const p = positions[node.id] ?? { x: 0, y: 0 };
      const data: PieNodeData = {
        possibility: node,
        busy: busyNodes.has(node.id),
        unexplored: unexplored.includes(node.id) || node.status === "unexplored",
        childCount: childCounts[node.id] ?? 0,
        simSummary: simulations[node.id]?.summary,
      };
      return {
        id: node.id,
        type: "possibility",
        position: { x: p.x, y: p.y },
        data: data as unknown as Record<string, unknown>,
        selected: selectedId === node.id,
        deletable: false,
      };
    });
  }, [nodes, positions, busyNodes, unexplored, simulations, selectedId]);

  const rfEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: "pie",
        deletable: false,
      })),
    [edges]
  );

  // Re-fit when the first batch of nodes arrives and again on completion —
  // nodes stream in after mount, so the initial fitView alone isn't enough.
  const prevCount = useRef(0);
  useEffect(() => {
    const count = rfNodes.length;
    const firstArrival = prevCount.current === 0 && count > 0;
    prevCount.current = count;
    if (firstArrival || analysisStatus === "completed") {
      const t = setTimeout(() => {
        void rf.fitView({ padding: 0.22, duration: 500, maxZoom: 1.05 });
      }, firstArrival ? 400 : 150);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [rfNodes.length, analysisStatus, rf]);

  // Track a live node for the minimap colouring
  const minimapNodeColor = (node: Node) => {
    const data = node.data as unknown as PieNodeData;
    const status = data.possibility.status;
    if (status === "alternative") return "#818cf8";
    if (status === "unexplored") return "#3f4663";
    if (data.busy) return "#22d3ee";
    return "#1d4ed8";
  };

  return (
    <div className="canvas-wrap">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.22, maxZoom: 1.05 }}
        minZoom={0.15}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnScroll
        zoomOnPinch
        aria-label="Scenario exploration graph"
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1a2138" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={minimapNodeColor}
          maskColor="rgba(4, 6, 12, 0.72)"
          style={{ background: "#0a0e1a", width: 150, height: 100 }}
          ariaLabel="Graph minimap"
        />
      </ReactFlow>
    </div>
  );
}

export default function Canvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

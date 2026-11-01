/**
 * Tidy tree layout for the scenario graph.
 * Root on the left, depth increases to the right; siblings stack vertically;
 * parents center on their children. Deterministic — driven by event order.
 */

import type { GraphEdgeRecord, Possibility } from "./types";

export interface Positioned {
  id: string;
  x: number;
  y: number;
}

const NODE_W = 250;
const NODE_H = 132;
const GAP_X = 120;
const GAP_Y = 28;

export function layoutGraph(
  nodes: Record<string, Possibility>,
  edges: GraphEdgeRecord[]
): Record<string, Positioned> {
  const ids = Object.keys(nodes);
  if (ids.length === 0) return {};

  // children map from event-flow edges (ignore back-refs for layout)
  const childrenOf: Record<string, string[]> = {};
  const parentOf: Record<string, string[]> = {};
  for (const edge of edges) {
    if (edge.relationship === "MODIFIES" || edge.relationship === "CONTRADICTS") continue;
    (childrenOf[edge.source] ??= []).push(edge.target);
    (parentOf[edge.target] ??= []).push(edge.source);
  }
  // fall back to parent_ids if an edge is missing
  for (const node of Object.values(nodes)) {
    for (const parent of node.parent_ids) {
      if (!(childrenOf[parent]?.includes(node.id))) {
        (childrenOf[parent] ??= []).push(node.id);
        (parentOf[node.id] ??= []).push(parent);
      }
    }
  }

  const roots = ids.filter((id) => !(parentOf[id] && parentOf[id].length));
  const placed = new Set<string>();
  const pos: Record<string, Positioned> = {};

  let cursorY = 0;
  const visited = new Set<string>();

  function place(id: string, depth: number): number {
    if (visited.has(id)) return pos[id]?.y ?? cursorY;
    visited.add(id);
    const kids = (childrenOf[id] ?? []).filter((k) => !visited.has(k));
    let y: number;
    if (kids.length === 0) {
      y = cursorY;
      cursorY += NODE_H + GAP_Y;
    } else {
      const kidYs = kids.map((k) => place(k, depth + 1));
      y = (kidYs[0] + kidYs[kidYs.length - 1]) / 2;
    }
    pos[id] = { id, x: depth * (NODE_W + GAP_X), y };
    placed.add(id);
    return y;
  }

  for (const root of roots.length ? roots : [ids[0]]) {
    place(root, 0);
    cursorY += GAP_Y;
  }
  // any unreachable nodes (shouldn't happen) appended at the end
  for (const id of ids) {
    if (!pos[id]) {
      pos[id] = { id, x: 0, y: cursorY };
      cursorY += NODE_H + GAP_Y;
    }
  }
  return pos;
}

export const NODE_SIZE = { width: NODE_W, height: NODE_H };

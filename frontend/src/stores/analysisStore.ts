/**
 * Client graph state (Zustand).
 *
 * Ground rules from §8.5/§9: the UI NEVER invents intelligence events.
 * Nodes and edges appear only when the backend reports them. Animation state
 * (fresh edges, exploring pulse) derives from real event arrival.
 */

import { create } from "zustand";
import type {
  AnalysisEvent,
  AnalysisStatus,
  GraphEdgeRecord,
  GraphSnapshot,
  Possibility,
  RelationshipType,
  SimulationInfo,
} from "../types";
import { layoutGraph } from "../layout";
import * as api from "../services/api";

export interface FeedItem {
  sequence: number;
  type: string;
  time: string;
  detail: string;
}

interface PieStore {
  // session
  phase: "input" | "exploring";
  analysisId: string | null;
  analysisStatus: AnalysisStatus;
  domains: string[];
  decision: string;
  unexplored: string[];
  streamState: "idle" | "connecting" | "live" | "closed";
  latestSequence: number;
  submitting: boolean;
  busyNodes: Set<string>;
  error: string | null;

  // graph data
  nodes: Record<string, Possibility>;
  edges: GraphEdgeRecord[];
  positions: ReturnType<typeof layoutGraph>;
  freshEdges: Set<string>;
  simulations: Record<string, SimulationInfo>;

  // interaction
  selectedId: string | null;
  feed: FeedItem[];

  // actions
  startAnalysis: (decision: string) => Promise<void>;
  applyEvent: (event: AnalysisEvent) => void;
  setStreamState: (state: "connecting" | "live" | "closed") => void;
  reconcile: () => Promise<void>;
  hydrateScenario: (id: string) => Promise<void>;
  select: (id: string | null) => void;
  reset: () => void;
  markEdgeSettled: (edgeId: string) => void;
}

let closeStream: (() => void) | null = null;

function recompute(set: (partial: Partial<PieStore>) => void, get: () => PieStore) {
  const { nodes, edges } = get();
  set({ positions: layoutGraph(nodes, edges) });
}

export const usePieStore = create<PieStore>((set, get) => ({
  phase: "input",
  analysisId: null,
  analysisStatus: "created",
  domains: [],
  decision: "",
  unexplored: [],
  streamState: "idle",
  latestSequence: 0,
  submitting: false,
  busyNodes: new Set(),
  error: null,
  nodes: {},
  edges: [],
  positions: {},
  freshEdges: new Set(),
  simulations: {},
  selectedId: null,
  feed: [],

  async startAnalysis(decision: string) {
    if (get().submitting) return;
    closeStream?.();
    set({
      submitting: true,
      error: null,
      nodes: {},
      edges: [],
      positions: {},
      freshEdges: new Set(),
      simulations: {},
      feed: [],
      busyNodes: new Set(),
      latestSequence: 0,
      decision,
      phase: "exploring",
      analysisStatus: "running",
      domains: [],
      unexplored: [],
      selectedId: null,
    });
    try {
      const { analysis_id } = await api.createAnalysis({
        decision,
        idempotency_key: `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      });
      set({ analysisId: analysis_id, submitting: false });
      closeStream = api.openEventStream(
        analysis_id,
        0,
        (event) => get().applyEvent(event),
        (state) => get().setStreamState(state)
      );
    } catch (err) {
      set({
        submitting: false,
        error: err instanceof Error ? err.message : String(err),
        analysisStatus: "failed",
      });
    }
  },

  setStreamState(state) {
    set({ streamState: state });
  },

  applyEvent(event) {
    const { nodes, edges, busyNodes, feed, simulations } = get();
    const nextNodes = { ...nodes };
    const nextBusy = new Set(busyNodes);
    let nextEdges = edges;
    const newFresh = new Set(get().freshEdges);

    const pushFeed = (detail: string) => {
      const item: FeedItem = {
        sequence: event.sequence,
        type: event.event_type,
        time: event.timestamp,
        detail,
      };
      set({ feed: [item, ...feed].slice(0, 40) });
    };

    switch (event.event_type) {
      case "analysis_started": {
        pushFeed(`Exploring: “${String(event.payload.decision ?? "").slice(0, 80)}”`);
        break;
      }
      case "domain_identified": {
        const all = (event.payload.all ?? []) as { domain: string }[];
        set({ domains: all.map((d) => d.domain) });
        pushFeed(`Domain: ${event.payload.primary}`);
        break;
      }
      case "possibility_discovered": {
        if (event.node_id) {
          const base: Possibility = {
            id: event.node_id,
            analysis_id: event.analysis_id,
            parent_ids: event.parent_ids ?? [],
            title: event.payload.title ?? "…",
            description: event.payload.description ?? "",
            depth: event.payload.depth ?? 0,
            status: (event.payload.status ?? "exploring") as Possibility["status"],
            domain: get().domains[0] ?? "general",
            conditions: [],
            triggers: [],
            causes: [],
            dependencies: [],
            consequences: [],
            time_horizon: { minimum: null, maximum: null, unit: "months" },
            probability: {
              status: "unquantified",
              estimate: null,
              interval: null,
              method: null,
              rationale: null,
            },
            impact: {
              level: (event.payload.impact ?? "moderate") as Possibility["impact"]["level"],
              explanation: "",
            },
            evidence: [],
            assumptions: [],
            priorities: {},
            model_version: "…",
            created_at: event.timestamp,
          };
          nextNodes[event.node_id] = base;
          nextBusy.add(event.node_id);
          for (const parentId of event.parent_ids ?? []) {
            const edgeId = `live-${parentId}->${event.node_id}`;
            if (!nextEdges.some((e) => e.source === parentId && e.target === event.node_id)) {
              nextEdges = [
                ...nextEdges,
                {
                  id: edgeId,
                  source: parentId,
                  target: event.node_id,
                  relationship: "MAY_CAUSE",
                  label: "",
                },
              ];
              newFresh.add(edgeId);
            }
          }
          // hydrate full node detail in the background (real fetch, not invention)
          void get().hydrateScenario(event.node_id);
        }
        pushFeed(event.payload.title ?? "possibility discovered");
        break;
      }
      case "possibility_validated": {
        if (event.node_id && nextNodes[event.node_id]) {
          nextNodes[event.node_id] = {
            ...nextNodes[event.node_id],
            status: (event.payload.status ?? "validated") as Possibility["status"],
          };
          nextBusy.delete(event.node_id);
        }
        break;
      }
      case "branch_expanded": {
        if (event.node_id) nextBusy.add(event.node_id);
        pushFeed(event.payload.what_if ? "what-if branch requested" : `expanding: ${event.payload.title ?? ""}`);
        break;
      }
      case "evidence_added": {
        if (event.node_id && nextNodes[event.node_id]) {
          nextNodes[event.node_id] = {
            ...nextNodes[event.node_id],
            evidence: event.payload.evidence ?? nextNodes[event.node_id].evidence,
            assumptions:
              event.payload.assumptions ?? nextNodes[event.node_id].assumptions,
          };
        }
        pushFeed(`evidence attached (${(event.payload.assumptions ?? []).length} assumptions)`);
        break;
      }
      case "estimate_updated": {
        if (event.node_id && nextNodes[event.node_id]) {
          nextNodes[event.node_id] = {
            ...nextNodes[event.node_id],
            probability: event.payload.probability,
          };
        }
        const p = event.payload.probability ?? {};
        pushFeed(
          p.status === "quantified"
            ? `estimate updated: P=${p.estimate} (${p.method})`
            : "estimate: unquantified"
        );
        break;
      }
      case "simulation_completed": {
        if (event.node_id) {
          simulations[event.node_id] = {
            kind: event.payload.kind,
            summary: event.payload.summary,
            metrics: event.payload.metrics ?? {},
            samples: event.payload.samples ?? 0,
          };
        }
        pushFeed(`simulation: ${event.payload.summary ?? event.payload.kind}`);
        break;
      }
      case "branch_completed": {
        if (event.node_id) nextBusy.delete(event.node_id);
        break;
      }
      case "context_required": {
        pushFeed(event.payload.detail ?? "context required");
        break;
      }
      case "analysis_completed": {
        set({
          analysisStatus: "completed",
          unexplored: event.payload.unexplored_branches ?? [],
        });
        pushFeed(
          `completed — ${event.payload.node_count} scenarios; unexplored branches marked`
        );
        void get().reconcile();
        break;
      }
      case "analysis_cancelled": {
        set({ analysisStatus: "cancelled" });
        pushFeed("analysis cancelled by user");
        break;
      }
      case "analysis_failed": {
        set({ analysisStatus: "failed", error: event.payload.error ?? "failed" });
        pushFeed(`failed: ${event.payload.error ?? ""}`);
        break;
      }
      default:
        pushFeed(event.event_type);
    }

    set({
      nodes: nextNodes,
      edges: nextEdges,
      busyNodes: nextBusy,
      freshEdges: newFresh,
      latestSequence: Math.max(get().latestSequence, event.sequence),
      simulations: { ...simulations },
    });
    recompute(set, get);
  },

  markEdgeSettled(edgeId) {
    const fresh = new Set(get().freshEdges);
    fresh.delete(edgeId);
    set({ freshEdges: fresh });
  },

  async hydrateScenario(id: string) {
    try {
      const full = await api.fetchScenario(id);
      const current = get().nodes[id];
      if (!current) return; // analysis reset meanwhile
      set({
        nodes: { ...get().nodes, [id]: { ...full, status: current.status } },
      });
      recompute(set, get);
    } catch {
      /* scenario may not be queryable yet; the event payload already shows it */
    }
  },

  /**
   * Reconcile with the authoritative graph snapshot. Used after completion,
   * expansion and what-if so edges/statuses always match the backend truth
   * (e.g. ALTERNATIVE_TO / MODIFIES edges the live events don't carry).
   */
  async reconcile() {
    const analysisId = get().analysisId;
    if (!analysisId) return;
    try {
      const snapshot: GraphSnapshot = await api.fetchGraph(analysisId);
      const { nodes: currentNodes, busyNodes } = get();
      const merged: Record<string, Possibility> = {};
      for (const [id, node] of Object.entries(snapshot.graph.nodes)) {
        const live = currentNodes[id];
        merged[id] = live && busyNodes.has(id) ? { ...node, status: live.status } : node;
      }
      set({
        nodes: merged,
        edges: snapshot.graph.edges,
        analysisStatus: snapshot.analysis.status,
        domains: snapshot.analysis.domains,
        unexplored: snapshot.analysis.unexplored_branches,
        latestSequence: Math.max(get().latestSequence, snapshot.latest_sequence),
        busyNodes: new Set(
          [...busyNodes].filter((id) => merged[id]?.status === "exploring")
        ),
      });
      recompute(set, get);
    } catch {
      /* offline or analysis gone — keep live state */
    }
  },

  select(id) {
    set({ selectedId: id });
    if (id) void get().hydrateScenario(id);
  },

  reset() {
    closeStream?.();
    closeStream = null;
    set({
      phase: "input",
      analysisId: null,
      analysisStatus: "created",
      nodes: {},
      edges: [],
      positions: {},
      freshEdges: new Set(),
      simulations: {},
      selectedId: null,
      feed: [],
      domains: [],
      unexplored: [],
      latestSequence: 0,
      streamState: "idle",
      error: null,
      decision: "",
      busyNodes: new Set(),
    });
  },
}));

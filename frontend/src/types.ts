/** Client-side mirrors of the PIE backend contracts (§5, §9, §10). */

export type AnalysisStatus =
  | "created"
  | "running"
  | "completed"
  | "cancelled"
  | "failed";

export type ScenarioStatus =
  | "exploring"
  | "validated"
  | "alternative"
  | "unexplored"
  | "infeasible";

export type ImpactLevel = "low" | "moderate" | "high" | "critical";

export type RelationshipType =
  | "MAY_CAUSE"
  | "REQUIRES"
  | "PREVENTS"
  | "LEADS_TO"
  | "DEPENDS_ON"
  | "ALTERNATIVE_TO"
  | "CONTRADICTS"
  | "MODIFIES"
  | "CONVERGES_WITH";

export interface TimeHorizon {
  minimum: number | null;
  maximum: number | null;
  unit: string;
}

export interface ProbabilityObject {
  status: "quantified" | "unquantified";
  estimate: number | null;
  interval: [number, number] | number[] | null;
  method: "data_backed" | "model_based" | "expert_elicited" | "unquantified" | null;
  rationale: string | null;
}

export interface ImpactObject {
  level: ImpactLevel;
  explanation: string;
}

export interface EvidenceRef {
  id: string;
  kind: "user_fact" | "external" | "assumption" | "model";
  claim: string;
  provenance: string;
  observed_at: string;
}

export interface Assumption {
  id: string;
  statement: string;
  is_blocking: boolean;
}

export interface Possibility {
  id: string;
  analysis_id: string;
  parent_ids: string[];
  title: string;
  description: string;
  depth: number;
  status: ScenarioStatus;
  domain: string;
  conditions: string[];
  triggers: string[];
  causes: string[];
  dependencies: string[];
  consequences: string[];
  time_horizon: TimeHorizon;
  probability: ProbabilityObject;
  impact: ImpactObject;
  evidence: EvidenceRef[];
  assumptions: Assumption[];
  priorities: Record<string, number>;
  model_version: string;
  created_at: string;
}

export interface GraphEdgeRecord {
  id: string;
  source: string;
  target: string;
  relationship: RelationshipType;
  label: string;
}

export interface AnalysisEvent {
  event_id: string;
  sequence: number;
  event_type: string;
  analysis_id: string;
  node_id: string | null;
  parent_ids: string[];
  timestamp: string;
  payload: Record<string, any>;
}

export interface GraphSnapshot {
  analysis: {
    id: string;
    status: AnalysisStatus;
    domains: string[];
    summary: string | null;
    unexplored_branches: string[];
    initial_state: { decision: string };
  };
  graph: {
    analysis_id: string;
    nodes: Record<string, Possibility>;
    edges: GraphEdgeRecord[];
  };
  latest_sequence: number;
}

export interface SimulationInfo {
  kind: string;
  summary: string;
  metrics: Record<string, number>;
  samples: number;
}

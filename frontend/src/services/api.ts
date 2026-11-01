/** REST + SSE client (§9, §10). All same-origin; dev server proxies to :8000. */

import type { AnalysisEvent, GraphSnapshot, Possibility } from "../types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function createAnalysis(body: {
  decision: string;
  goal?: string;
  idempotency_key?: string;
}): Promise<{ analysis_id: string; status: string }> {
  return json(
    await fetch("/v1/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function fetchGraph(analysisId: string): Promise<GraphSnapshot> {
  return json(await fetch(`/v1/analyses/${analysisId}/graph`));
}

export async function fetchScenario(scenarioId: string): Promise<Possibility> {
  return json(await fetch(`/v1/scenarios/${scenarioId}`));
}

export async function cancelAnalysis(analysisId: string): Promise<{ cancelled: boolean }> {
  return json(
    await fetch(`/v1/analyses/${analysisId}/cancel`, { method: "POST" })
  );
}

export async function expandScenario(scenarioId: string): Promise<{ expanded: string }> {
  return json(
    await fetch(`/v1/scenarios/${scenarioId}/expand`, { method: "POST" })
  );
}

export async function whatIf(
  scenarioId: string,
  modification: string,
  assumptionChange?: string
): Promise<{ alternative_id: string; based_on: string }> {
  return json(
    await fetch(`/v1/scenarios/${scenarioId}/what-if`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        modification,
        assumption_change: assumptionChange || null,
      }),
    })
  );
}

/**
 * Subscribe to the analysis event stream.
 * EventSource auto-reconnects with Last-Event-ID; we pass the cursor as a
 * query param for the first connection so replay covers missed events.
 */
export function openEventStream(
  analysisId: string,
  lastSequence: number,
  onEvent: (event: AnalysisEvent) => void,
  onStatus: (state: "connecting" | "live" | "closed") => void
): () => void {
  const source = new EventSource(
    `/v1/analyses/${analysisId}/events?last_event_id=${lastSequence}`
  );
  onStatus("connecting");

  const handler = (event: MessageEvent) => {
    try {
      const parsed = JSON.parse(event.data) as AnalysisEvent;
      onEvent(parsed);
    } catch {
      /* ignore malformed frames */
    }
  };

  // Named events (per §9 event_type) plus the generic message channel.
  const types = [
    "analysis_started",
    "context_required",
    "context_received",
    "domain_identified",
    "possibility_discovered",
    "possibility_validated",
    "branch_expanded",
    "estimate_updated",
    "simulation_completed",
    "evidence_added",
    "branch_completed",
    "analysis_completed",
    "analysis_failed",
    "analysis_cancelled",
  ];
  source.onopen = () => onStatus("live");
  source.onerror = () => onStatus("closed");
  source.onmessage = handler;
  for (const type of types) source.addEventListener(type, handler as EventListener);

  return () => {
    source.close();
    onStatus("closed");
  };
}

/**
 * Branch detail inspector (§8.2): causes, conditions, consequences,
 * probability provenance, assumptions, evidence — plus expand and what-if.
 */

import { useState } from "react";
import { usePieStore } from "../stores/analysisStore";
import * as api from "../services/api";

export default function Inspector() {
  const selectedId = usePieStore((s) => s.selectedId);
  const node = usePieStore((s) => (s.selectedId ? s.nodes[s.selectedId] : null));
  const busy = usePieStore((s) => (s.selectedId ? s.busyNodes.has(s.selectedId) : false));
  const simulation = usePieStore((s) => (s.selectedId ? s.simulations[s.selectedId] : undefined));
  const unexplored = usePieStore((s) =>
    s.selectedId ? s.unexplored.includes(s.selectedId) : false
  );
  const select = usePieStore((s) => s.select);
  const reconcile = usePieStore((s) => s.reconcile);
  const applyEvent = usePieStore((s) => s.applyEvent);

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [whatIfOpen, setWhatIfOpen] = useState(false);
  const [modification, setModification] = useState("");
  const [assumption, setAssumption] = useState("");

  if (!selectedId || !node) {
    return (
      <aside className="inspector inspector-empty">
        <h2>Branch inspector</h2>
        <p className="muted">
          Select a scenario node to inspect its causes, conditions, evidence and
          uncertainty — then expand it or fork a what-if.
        </p>
        <div className="legend">
          <h3>Visual language</h3>
          <ul>
            <li><span className="legend-swatch exploring" /> rainbow glow — backend is exploring</li>
            <li><span className="legend-swatch settled" /> steady blue — validated scenario</li>
            <li><span className="legend-swatch alternative" /> dashed indigo — what-if alternative</li>
            <li><span className="legend-swatch unexplored" /> dashed grey — unexplored branch</li>
            <li><span className="legend-dot" /> colour = impact · <span className="legend-prob">P?</span> = unquantified probability</li>
          </ul>
        </div>
      </aside>
    );
  }

  const p = node.probability;

  const doExpand = async () => {
    setBusyAction("expand");
    setActionError(null);
    try {
      await api.expandScenario(node.id);
      // events stream in; reconcile shortly after backend admits children
      setTimeout(() => void reconcile(), 4500);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  const doWhatIf = async () => {
    if (modification.trim().length < 4) return;
    setBusyAction("whatif");
    setActionError(null);
    try {
      await api.whatIf(node.id, modification.trim(), assumption.trim() || undefined);
      setWhatIfOpen(false);
      setModification("");
      setAssumption("");
      setTimeout(() => void reconcile(), 3500);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <aside className="inspector" aria-label="Scenario details">
      <div className="inspector-head">
        <div className="inspector-kicker">
          <span className="depth-badge">d{node.depth}</span>
          <span className={`status-pill ${node.status}`}>{node.status}</span>
          <button className="close-btn" onClick={() => select(null)} aria-label="Close inspector">✕</button>
        </div>
        <h2>{node.title}</h2>
        {node.description && <p className="desc">{node.description}</p>}
      </div>

      <section className="prob-panel">
        <h3>Probability</h3>
        {p.status === "quantified" ? (
          <>
            <div className="prob-value">
              {p.estimate !== null ? `${Math.round(p.estimate * 100)}%` : "—"}
              <span className="prob-method">{p.method?.replace("_", " ")}</span>
            </div>
            {p.interval && (
              <div className="muted small">
                interval: [{(p.interval as number[]).join(", ")}]
              </div>
            )}
            {p.rationale && <p className="rationale">{p.rationale}</p>}
          </>
        ) : (
          <div className="prob-unquantified">
            <span className="prob-big">unquantified</span>
            <p className="muted small">
              No defensible numerical estimate is available for this possibility.
              PIE does not invent probabilities — the scenario can still matter.
            </p>
          </div>
        )}
        {simulation && (
          <div className="sim-box">
            <h4>Simulation · {simulation.kind}</h4>
            <p className="small">{simulation.summary}</p>
            <p className="muted small">
              {simulation.samples} seeded samples — reproducible run
            </p>
          </div>
        )}
      </section>

      <section>
        <h3>Impact</h3>
        <div className="impact-line">
          <span className={`impact-dot impact-${node.impact.level}`} />
          <strong>{node.impact.level}</strong>
          <span className="muted small">{node.impact.explanation}</span>
        </div>
        <div className="muted small">Horizon: {horizon(node)}</div>
      </section>

      <ListSection title="Causes" items={node.causes} />
      <ListSection title="Conditions" items={node.conditions} />
      <ListSection title="Triggers" items={node.triggers} />
      <ListSection title="Consequences" items={node.consequences} />
      <ListSection title="Dependencies" items={node.dependencies} />

      <section>
        <h3>Assumptions <span className="count">{node.assumptions.length}</span></h3>
        {node.assumptions.length === 0 && <p className="muted small">None recorded.</p>}
        <ul className="assumption-list">
          {node.assumptions.map((a) => (
            <li key={a.id} className={a.is_blocking ? "blocking" : ""}>
              {a.is_blocking && <span className="blocking-tag">blocking</span>}
              {a.statement}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Evidence <span className="count">{node.evidence.length}</span></h3>
        {node.evidence.map((e) => (
          <div key={e.id} className="evidence-item">
            <span className={`evidence-kind ${e.kind}`}>{e.kind.replace("_", " ")}</span>
            <span>{e.claim}</span>
            <span className="muted small">— {e.provenance}</span>
          </div>
        ))}
      </section>

      {Object.keys(node.priorities).length > 0 && (
        <section>
          <h3>Branch priorities <span className="muted small">(dimensions kept separate)</span></h3>
          {Object.entries(node.priorities).map(([k, v]) => (
            <div key={k} className="prio-row">
              <span className="prio-key">{k.replace(/_/g, " ")}</span>
              <div className="prio-bar">
                <div className="prio-fill" style={{ width: `${Math.round(v * 100)}%` }} />
              </div>
              <span className="prio-val">{v.toFixed(2)}</span>
            </div>
          ))}
        </section>
      )}

      <div className="inspector-actions">
        <button
          className="primary-btn small"
          onClick={() => void doExpand()}
          disabled={busy || busyAction !== null || unexplored || node.depth >= 4}
          title={
            unexplored
              ? "No further coverage for this branch yet"
              : "Explore secondary consequences of this scenario"
          }
        >
          {busyAction === "expand" ? "Expanding…" : "Expand branch ↓"}
        </button>
        <button
          className="ghost-btn"
          onClick={() => setWhatIfOpen((v) => !v)}
          disabled={busyAction !== null}
        >
          What-if ⑂
        </button>
      </div>

      {whatIfOpen && (
        <div className="whatif-form">
          <p className="small">
            Modify one condition. The original scenario stays intact; PIE forks an
            alternative node linked with <code>ALTERNATIVE_TO</code> + <code>MODIFIES</code>.
          </p>
          <textarea
            rows={2}
            placeholder="e.g. We cut monthly burn to 1.8 lakh by pausing hiring"
            value={modification}
            onChange={(e) => setModification(e.target.value)}
          />
          <input
            placeholder="assumption override (optional) e.g. monthly_costs = 180000"
            value={assumption}
            onChange={(e) => setAssumption(e.target.value)}
          />
          <button
            className="primary-btn small"
            onClick={() => void doWhatIf()}
            disabled={modification.trim().length < 4 || busyAction !== null}
          >
            {busyAction === "whatif" ? "Forking…" : "Fork alternative scenario"}
          </button>
        </div>
      )}
      {actionError && <div className="error-note">{actionError}</div>}
      {unexplored && (
        <p className="muted small unexplored-note">
          This branch is marked <strong>unexplored</strong> — the graph does not
          claim completeness here.
        </p>
      )}
      <p className="muted small">model: {node.model_version} · id: {node.id}</p>
    </aside>
  );
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h3>{title} <span className="count">{items.length}</span></h3>
      <ul className="bullet-list">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function horizon(node: { time_horizon: { minimum: number | null; maximum: number | null; unit: string } }) {
  const h = node.time_horizon;
  if (h.minimum == null && h.maximum == null) return "unspecified";
  if (h.minimum === h.maximum) return `~${h.minimum} ${h.unit}`;
  return `${h.minimum ?? "?"}–${h.maximum ?? "?"} ${h.unit}`;
}

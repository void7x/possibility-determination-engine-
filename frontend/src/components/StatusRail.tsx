/** Analysis status rail + live computation feed (§8.2 items 8, event log §9). */

import { usePieStore } from "../stores/analysisStore";
import * as api from "../services/api";

export default function StatusRail() {
  const analysisStatus = usePieStore((s) => s.analysisStatus);
  const domains = usePieStore((s) => s.domains);
  const feed = usePieStore((s) => s.feed);
  const latestSequence = usePieStore((s) => s.latestSequence);
  const streamState = usePieStore((s) => s.streamState);
  const nodeCount = usePieStore((s) => Object.keys(s.nodes).length);
  const unexplored = usePieStore((s) => s.unexplored);
  const analysisId = usePieStore((s) => s.analysisId);
  const reset = usePieStore((s) => s.reset);

  const cancel = async () => {
    if (analysisId) await api.cancelAnalysis(analysisId);
  };

  return (
    <div className="status-rail">
      <div className="rail-top">
        <div className="rail-status">
          <span className={`status-dot ${analysisStatus}`} />
          <span className="status-text">{analysisStatus}</span>
          <span className={`stream-dot ${streamState}`} title={`event stream: ${streamState}`} />
        </div>
        <button className="ghost-btn small" onClick={() => reset()}>+ New analysis</button>
      </div>

      <div className="rail-metrics">
        <Metric label="scenarios" value={String(nodeCount)} />
        <Metric label="events" value={String(latestSequence)} />
        <Metric label="unexplored" value={String(unexplored.length)} warn={unexplored.length > 0} />
      </div>

      {domains.length > 0 && (
        <div className="rail-domains">
          {domains.map((d) => (
            <span key={d} className="domain-chip">{d.replace(/_/g, " & ")}</span>
          ))}
        </div>
      )}

      {analysisStatus === "running" && (
        <button className="ghost-btn small danger" onClick={() => void cancel()}>
          Cancel exploration
        </button>
      )}

      <div className="rail-feed">
        <h3>Computation feed</h3>
        <p className="muted small">Only real backend events appear here.</p>
        <ul>
          {feed.map((item) => (
            <li key={item.sequence}>
              <span className="feed-seq">#{item.sequence}</span>
              <span className={`feed-type ${item.type}`}>{item.type}</span>
              <span className="feed-detail">{item.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Metric({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className={`metric ${warn ? "warn" : ""}`}>
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

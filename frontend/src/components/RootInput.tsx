/** Root input screen: the entry point of the exploration space (§8.3 initial state). */

import { useState } from "react";
import { usePieStore } from "../stores/analysisStore";

const SEEDS = [
  {
    label: "Server migration",
    text: "Should we migrate our production servers to a new cloud provider?",
    hint: "technology & cybersecurity",
  },
  {
    label: "Launch a subscription tier",
    text: "Should we launch a subscription tier for our e-commerce business? We have about 12 lakh rupees in the bank and spend 3 lakh a month.",
    hint: "business & operations",
  },
  {
    label: "Change career path",
    text: "Should I quit my job to study full-time for a year?",
    hint: "personal & career",
  },
];

export default function RootInput() {
  const [text, setText] = useState("");
  const startAnalysis = usePieStore((s) => s.startAnalysis);
  const submitting = usePieStore((s) => s.submitting);
  const error = usePieStore((s) => s.error);

  const submit = () => {
    const decision = text.trim();
    if (decision.length < 8 || submitting) return;
    void startAnalysis(decision);
  };

  return (
    <div className="root-input-screen">
      <div className="root-input-card">
        <div className="brand-row">
          <div className="brand-mark" aria-hidden>
            <svg viewBox="0 0 48 48" width="42" height="42">
              <defs>
                <linearGradient id="brand-g" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#7c3aed" />
                  <stop offset="50%" stopColor="#06b6d4" />
                  <stop offset="100%" stopColor="#eab308" />
                </linearGradient>
              </defs>
              <circle cx="24" cy="24" r="6" fill="url(#brand-g)" />
              <circle cx="8" cy="12" r="3" fill="#3b82f6" />
              <circle cx="40" cy="10" r="3" fill="#22c55e" />
              <circle cx="42" cy="34" r="3" fill="#eab308" />
              <circle cx="10" cy="38" r="3" fill="#fb7185" />
              <path d="M8 12 L24 24 L40 10 M24 24 L42 34 M24 24 L10 38" stroke="#2c3550" strokeWidth="1.5" fill="none" />
            </svg>
          </div>
          <div>
            <h1>Possibility Intelligence Engine</h1>
            <p className="tagline">
              Enter a decision. PIE builds an explorable network of possible outcomes —
              causes, conditions, consequences and honest uncertainty.
            </p>
          </div>
        </div>

        <textarea
          className="root-textarea"
          placeholder="e.g. Should we migrate our production servers to a new cloud provider? …"
          value={text}
          rows={4}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          }}
          aria-label="Decision to explore"
        />

        <div className="seed-row">
          <span className="seed-label">Try:</span>
          {SEEDS.map((seed) => (
            <button key={seed.label} className="seed-chip" onClick={() => setText(seed.text)}>
              {seed.label} <span className="seed-hint">{seed.hint}</span>
            </button>
          ))}
        </div>

        <button
          className="primary-btn"
          disabled={text.trim().length < 8 || submitting}
          onClick={submit}
        >
          {submitting ? "Starting analysis…" : "Explore possibilities →"}
        </button>
        {error && <div className="error-note">{error}</div>}
        <p className="fine-print">
          Prototype slice: discovery runs on a deterministic, auditable provider so results are
          reproducible. Probability estimates appear only where an explicit model applies —
          everything else is marked unquantified, never invented.
        </p>
      </div>
    </div>
  );
}

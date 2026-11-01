import { usePieStore } from "./stores/analysisStore";
import RootInput from "./components/RootInput";
import Canvas from "./components/Canvas";
import Inspector from "./components/Inspector";
import StatusRail from "./components/StatusRail";

export default function App() {
  const phase = usePieStore((s) => s.phase);
  const decision = usePieStore((s) => s.decision);

  if (phase === "input") {
    return (
      <div className="app app-input">
        <RootInput />
      </div>
    );
  }

  return (
    <div className="app app-space">
      <header className="space-header">
        <div className="header-brand">
          <span className="header-mark" aria-hidden>◈</span> PIE
          <span className="header-sub">Possibility Exploration Space</span>
        </div>
        <div className="header-decision" title={decision}>
          {decision}
        </div>
      </header>
      <div className="space-body">
        <StatusRail />
        <main className="space-canvas">
          <Canvas />
        </main>
        <Inspector />
      </div>
    </div>
  );
}

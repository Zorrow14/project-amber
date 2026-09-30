import { lazy, Suspense } from "react";

import { useMeta } from "./context/metaContext";
import { useHashRoute, VIEWS, type View } from "./hooks/useHashRoute";

// Views load on demand, so the first paint does not wait on every chart.
const Overview = lazy(() => import("./views/Overview").then((m) => ({ default: m.Overview })));
const Past = lazy(() => import("./views/Past").then((m) => ({ default: m.Past })));
const Counterfactual = lazy(() =>
  import("./views/Counterfactual").then((m) => ({ default: m.Counterfactual })),
);
const Future = lazy(() => import("./views/Future").then((m) => ({ default: m.Future })));

const LABELS: Record<View, string> = {
  overview: "Overview",
  past: "Past",
  counterfactual: "Counterfactual",
  future: "Future",
};

export function App() {
  const meta = useMeta();
  const [view, navigate] = useHashRoute();

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner">
          <a className="brand" href="#/overview" aria-label="Amber - overview">
            <span className="brand__mark" aria-hidden="true" />
            Amber
          </a>
          <nav aria-label="Views">
            <ul className="tabs">
              {VIEWS.map((name) => (
                <li key={name}>
                  <a href={`#/${name}`} className="tab" aria-current={name === view ? "page" : undefined}>
                    {LABELS[name]}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main className="page">
        <Suspense fallback={<p className="muted">Loading…</p>}>
          {view === "overview" ? <Overview onNavigate={navigate} /> : null}
          {view === "past" ? <Past /> : null}
          {view === "counterfactual" ? <Counterfactual /> : null}
          {view === "future" ? <Future /> : null}
        </Suspense>
      </main>

      <footer className="footer">
        <p>{meta.framing.project}</p>
        <p className="muted">
          Data: World Bank WDI, served from the {meta.data.source} snapshot
          {meta.data.built_at ? ` built ${meta.data.built_at.slice(0, 10)}` : ""}
          {meta.data.commit ? ` (${meta.data.commit.slice(0, 7)})` : ""}.
        </p>
      </footer>
    </div>
  );
}

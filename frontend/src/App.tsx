import { lazy, Suspense, useEffect, useRef } from "react";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Loading } from "./components/LoadState";
import { useMeta } from "./context/metaContext";
import { parseView, useHashRoute, VIEWS, type View } from "./hooks/useHashRoute";

// Views load on demand, so the first paint does not wait on every chart.
const loaders = {
  overview: () => import("./views/Overview").then((m) => ({ default: m.Overview })),
  past: () => import("./views/Past").then((m) => ({ default: m.Past })),
  counterfactual: () => import("./views/Counterfactual").then((m) => ({ default: m.Counterfactual })),
  future: () => import("./views/Future").then((m) => ({ default: m.Future })),
} satisfies Record<View, unknown>;

// Start fetching the landing view's code now, in parallel with GET /meta, rather
// than after it: on a cold start the chunk arrives while the API is still waking.
loaders[parseView(window.location.hash)]().catch(() => {
  // A failed preload is retried by lazy() below, and its error shown there.
});

const Overview = lazy(loaders.overview);
const Past = lazy(loaders.past);
const Counterfactual = lazy(loaders.counterfactual);
const Future = lazy(loaders.future);

const LABELS: Record<View, string> = {
  overview: "Overview",
  past: "Past",
  counterfactual: "Counterfactual",
  future: "Future",
};

export function App() {
  const meta = useMeta();
  const [view, navigate] = useHashRoute();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  // On a view change, move focus to the new content so keyboard and screen-reader
  // users land on it rather than staying on the tab they pressed.
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
    window.scrollTo({ top: 0 });
  }, [view]);

  return (
    <div className="app">
      <a className="skip-link" href="#main" onClick={(event) => {
          event.preventDefault();
          main.current?.focus();
        }}>
        Skip to content
      </a>
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

      <main className="page" id="main" ref={main} tabIndex={-1} aria-label={LABELS[view]}>
        <ErrorBoundary resetKey={view}>
          <Suspense fallback={<Loading label={`Loading the ${LABELS[view].toLowerCase()} view…`} height={320} />}>
            {view === "overview" ? <Overview onNavigate={navigate} /> : null}
            {view === "past" ? <Past /> : null}
            {view === "counterfactual" ? <Counterfactual /> : null}
            {view === "future" ? <Future /> : null}
          </Suspense>
        </ErrorBoundary>
      </main>

      <footer className="footer">
        <p>{meta.framing.project}</p>
        <p className="muted">
          Data: World Bank WDI (CC BY 4.0), served from the {meta.data.source} snapshot
          {meta.data.built_at ? ` built ${meta.data.built_at.slice(0, 10)}` : ""}
          {meta.data.commit ? ` (${meta.data.commit.slice(0, 7)})` : ""}.
        </p>
      </footer>
    </div>
  );
}

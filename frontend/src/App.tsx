import { lazy, Suspense } from "react";

import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Loading } from "./components/LoadState";
import { useMeta } from "./context/metaContext";
import { parseView, useHashRoute, VIEWS, type View } from "./hooks/useHashRoute";
import { CHART } from "./lib/chartTokens";

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

  return (
    <AppShell
      views={VIEWS}
      labels={LABELS}
      current={view}
      footer={
        <>
          <p>{meta.framing.project}</p>
          <p className="num">
            Data: World Bank WDI (CC BY 4.0), served from the {meta.data.source} snapshot
            {meta.data.built_at ? ` built ${meta.data.built_at.slice(0, 10)}` : ""}
            {meta.data.commit ? ` (${meta.data.commit.slice(0, 7)})` : ""}.
          </p>
        </>
      }
    >
      <ErrorBoundary resetKey={view}>
        <Suspense fallback={<Loading label={`Loading the ${LABELS[view].toLowerCase()} view…`} height={CHART.height} />}>
          {view === "overview" ? <Overview onNavigate={navigate} /> : null}
          {view === "past" ? <Past /> : null}
          {view === "counterfactual" ? <Counterfactual /> : null}
          {view === "future" ? <Future /> : null}
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}

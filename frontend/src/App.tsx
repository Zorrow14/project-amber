import { lazy, Suspense } from "react";

import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Loading } from "./components/LoadState";
import { useMeta } from "./context/metaContext";
import { parseView, useHashRoute, VIEWS, type View } from "./hooks/useHashRoute";
import { useI18n } from "./i18n/context";
import { CHART } from "./lib/chartTokens";

// Views load on demand, so the first paint does not wait on every chart.
const loaders = {
  overview: () => import("./views/Overview").then((m) => ({ default: m.Overview })),
  history: () => import("./views/History").then((m) => ({ default: m.History })),
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
const History = lazy(loaders.history);
const Past = lazy(loaders.past);
const Counterfactual = lazy(loaders.counterfactual);
const Future = lazy(loaders.future);

/**
 * The footer's translation-status note: shown in Burmese while any Burmese caveat
 * - the app's own (`my.json` `_review`) or the API's (`/meta`) - awaits review.
 */
export function TranslationNote({ apiPending = 0 }: { apiPending?: number }) {
  const { locale, reviewPending, t } = useI18n();
  if (locale === "en" || !(reviewPending || apiPending > 0)) return null;
  return (
    <p className="translation-note" data-translation-note>
      {t("app.translationNote")}
    </p>
  );
}

export function App() {
  const meta = useMeta();
  const { t } = useI18n();
  const [view, navigate] = useHashRoute();
  const labels = Object.fromEntries(VIEWS.map((name) => [name, t(`nav.${name}`)])) as Record<View, string>;
  const source = meta.data.source === "release" ? t("meta.sourceRelease") : t("meta.sourceProcessed");

  return (
    <AppShell
      views={VIEWS}
      labels={labels}
      current={view}
      footer={
        <>
          <p>{meta.framing.project}</p>
          <p className="num">
            {t("app.footerData", {
              source,
              build: meta.data.built_at ? t("app.footerBuild", { date: meta.data.built_at.slice(0, 10) }) : "",
              commit: meta.data.commit ? t("app.footerCommit", { commit: meta.data.commit.slice(0, 7) }) : "",
            })}
          </p>
          <TranslationNote apiPending={meta.translation_review_pending} />
        </>
      }
    >
      <ErrorBoundary resetKey={view}>
        <Suspense fallback={<Loading label={t("app.loadingView", { view: labels[view].toLowerCase() })} height={CHART.height} />}>
          {view === "overview" ? <Overview onNavigate={navigate} /> : null}
          {view === "history" ? <History /> : null}
          {view === "past" ? <Past /> : null}
          {view === "counterfactual" ? <Counterfactual /> : null}
          {view === "future" ? <Future /> : null}
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}

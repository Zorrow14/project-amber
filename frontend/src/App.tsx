import { Fragment, lazy, Suspense } from "react";

import type { Meta } from "./api/types";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Loading } from "./components/LoadState";
import { MetaProvider } from "./context/meta";
import { useOptionalMeta } from "./context/metaContext";
import { Link } from "./context/route";
import { useRoute } from "./context/routeContext";
import { useI18n } from "./i18n/context";
import { CHART } from "./lib/chartTokens";
import { parseLocation, SOURCES_ANCHOR, VIEWS, type View } from "./lib/url";

// Views load on demand, so the first paint does not wait on every chart.
const loaders = {
  about: () => import("./views/About").then((m) => ({ default: m.About })),
  overview: () => import("./views/Overview").then((m) => ({ default: m.Overview })),
  history: () => import("./views/History").then((m) => ({ default: m.History })),
  past: () => import("./views/Past").then((m) => ({ default: m.Past })),
  counterfactual: () => import("./views/Counterfactual").then((m) => ({ default: m.Counterfactual })),
  future: () => import("./views/Future").then((m) => ({ default: m.Future })),
} satisfies Record<View, unknown>;

// Start fetching the landing view's code now, in parallel with GET /meta, rather
// than after it: on a cold start the chunk arrives while the API is still waking.
loaders[parseLocation(window.location.search, window.location.hash).view]().catch(() => {
  // A failed preload is retried by lazy() below, and its error shown there.
});

const About = lazy(loaders.about);
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

/**
 * The app. About needs nothing from the API, so it renders at once - a reader
 * on a cold start reads it while the server wakes; every other view waits for
 * GET /meta behind the boot screen.
 */
export function App() {
  const { view } = useRoute();
  return (
    <MetaProvider bootless={view === "about"}>
      <Views />
    </MetaProvider>
  );
}

function Footer({ meta }: { meta: Meta | null }) {
  const { t } = useI18n();
  const source = meta?.data.source === "release" ? t("meta.sourceRelease") : t("meta.sourceProcessed");
  return (
    <>
      {meta ? <p>{meta.framing.project}</p> : null}
      <p className="num">
        {meta
          ? `${t("app.footerData", {
              source,
              build: meta.data.built_at ? t("app.footerBuild", { date: meta.data.built_at.slice(0, 10) }) : "",
              commit: meta.data.commit ? t("app.footerCommit", { commit: meta.data.commit.slice(0, 7) }) : "",
            })} `
          : null}
        <Link view="about" anchor={SOURCES_ANCHOR} className="shell-footer__sources">
          {t("sources.link")}
        </Link>
      </p>
      <TranslationNote apiPending={meta?.translation_review_pending} />
    </>
  );
}

function Views() {
  const meta = useOptionalMeta();
  const { t } = useI18n();
  const { view, restored } = useRoute();
  const labels = Object.fromEntries(VIEWS.map((name) => [name, t(`nav.${name}`)])) as Record<View, string>;

  return (
    <AppShell views={VIEWS} labels={labels} current={view} footer={<Footer meta={meta} />}>
      <ErrorBoundary resetKey={view}>
        <Suspense fallback={<Loading label={t("app.loadingView", { view: labels[view].toLowerCase() })} height={CHART.height} />}>
          {/* Back and Forward restore a view's state from the URL, so they remount it. */}
          <Fragment key={restored}>
            {view === "about" ? <About /> : null}
            {view === "overview" ? <Overview /> : null}
            {view === "history" ? <History /> : null}
            {view === "past" ? <Past /> : null}
            {view === "counterfactual" ? <Counterfactual /> : null}
            {view === "future" ? <Future /> : null}
          </Fragment>
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}

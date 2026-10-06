import type { ReactNode } from "react";

import { api, API_BASE_URL } from "../api/client";
import { FetchError, Loading, Waking } from "../components/LoadState";
import { useApi } from "../hooks/useApi";
import { useI18n } from "../i18n/context";
import { MetaContext } from "./metaContext";

/**
 * Loads GET /meta once; everything the UI shows is derived from it. This is the
 * app's first request, so it is the one that meets a sleeping server: it keeps
 * retrying for up to a minute and a half, and says why, before giving up.
 *
 * `bootless` renders the children before /meta arrives, for a page that needs
 * nothing from it (About): useOptionalMeta() is null until it does.
 */
export function MetaProvider({ children, bootless = false }: { children: ReactNode; bootless?: boolean }) {
  const state = useApi(api.meta, "meta");
  const { t, tNodes } = useI18n();

  if (state.data) return <MetaContext.Provider value={state.data}>{children}</MetaContext.Provider>;
  if (bootless) return children;
  return (
    <main className="boot">
      <div className="boot__inner">
        <p className="boot__brand">
          <span className="brand__mark" aria-hidden="true" /> {t("app.brand")}
        </p>
        {state.error ? (
          <FetchError error={state.error} what={t("app.bootWhat")} onRetry={state.retry} />
        ) : state.waking ? (
          <Waking since={state.since} onRetry={state.retry} />
        ) : (
          <Loading label={t("app.bootLoading")} />
        )}
        {state.error && import.meta.env.DEV ? (
          <p className="muted">
            {tNodes("app.devHint", {
              command: <code>make api</code>,
              variable: <code>VITE_API_BASE_URL</code>,
              url: <code>{API_BASE_URL}</code>,
            })}
          </p>
        ) : null}
      </div>
    </main>
  );
}

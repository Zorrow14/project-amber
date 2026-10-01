import type { ReactNode } from "react";

import { api, API_BASE_URL } from "../api/client";
import { FetchError, Loading, Waking } from "../components/LoadState";
import { useApi } from "../hooks/useApi";
import { MetaContext } from "./metaContext";

/**
 * Loads GET /meta once; everything the UI shows is derived from it. This is the
 * app's first request, so it is the one that meets a sleeping server: it keeps
 * retrying for up to a minute and a half, and says why, before giving up.
 */
export function MetaProvider({ children }: { children: ReactNode }) {
  const state = useApi(api.meta, "meta");

  if (state.data) return <MetaContext.Provider value={state.data}>{children}</MetaContext.Provider>;
  return (
    <main className="page page--center">
      <div className="boot">
        <p className="boot__brand">
          <span className="brand__mark" aria-hidden="true" /> Amber
        </p>
        {state.error ? (
          <FetchError error={state.error} what="Amber's model data" onRetry={state.retry} />
        ) : state.waking ? (
          <Waking since={state.since} onRetry={state.retry} />
        ) : (
          <Loading label="Loading Amber…" />
        )}
        {state.error && import.meta.env.DEV ? (
          <p className="muted">
            Developing locally? Start the API with <code>make api</code>, or point{" "}
            <code>VITE_API_BASE_URL</code> at a running instance (currently <code>{API_BASE_URL}</code>).
          </p>
        ) : null}
      </div>
    </main>
  );
}

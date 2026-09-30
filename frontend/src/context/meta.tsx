import type { ReactNode } from "react";

import { api, API_BASE_URL } from "../api/client";
import { useApi } from "../hooks/useApi";
import { MetaContext } from "./metaContext";

/** Loads GET /meta once; everything the UI shows is derived from it. */
export function MetaProvider({ children }: { children: ReactNode }) {
  const { data, error } = useApi(api.meta, "meta");

  if (error) {
    return (
      <main className="page page--center">
        <div className="notice notice--critical" role="alert">
          <strong>The Amber API is unavailable.</strong>
          <p>
            {error.message}. Start it with <code>make api</code>, or point{" "}
            <code>VITE_API_BASE_URL</code> at a running instance (currently{" "}
            <code>{API_BASE_URL}</code>).
          </p>
        </div>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="page page--center">
        <p className="muted">Loading Amber…</p>
      </main>
    );
  }
  return <MetaContext.Provider value={data}>{children}</MetaContext.Provider>;
}

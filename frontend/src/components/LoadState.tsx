import { useEffect, useState, type ReactNode } from "react";

import { describeError } from "../api/client";
import type { ApiState } from "../hooks/useApi";
import { Notice } from "./Notice";

/** Whole seconds since `since`, ticking once a second. */
function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since == null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [since]);
  return since == null ? 0 : Math.max(0, Math.round((now - since) / 1000));
}

export function Loading({ label, height }: { label: string; height?: number }) {
  return (
    <div className="loading" role="status" style={height ? { minHeight: height } : undefined}>
      <span className="loading__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

/**
 * The cold-start state. The hosted API sleeps when idle and takes up to a
 * minute to wake; say so plainly, keep retrying, and offer a manual retry.
 */
export function Waking({ since, onRetry }: { since: number | null; onRetry: () => void }) {
  const elapsed = useElapsed(since);
  return (
    <Notice tone="info" title="Waking the server - this can take up to a minute" role="status">
      <p>
        Amber's API runs on a free hosting tier that sleeps when nobody is using it. The first request
        after a pause starts it up again; this page keeps retrying on its own.
      </p>
      <div className="notice__actions">
        <button type="button" className="button" onClick={onRetry}>
          Retry now
        </button>
        {since != null ? (
          <span className="muted" aria-hidden="true">
            Waiting {elapsed} s
          </span>
        ) : null}
      </div>
    </Notice>
  );
}

export function FetchError({
  error,
  what,
  onRetry,
  inputTitle,
  note,
}: {
  error: Error;
  what: string;
  onRetry: () => void;
  /** Title for a rejected (422) request, where the cause is the reader's input. */
  inputTitle?: string;
  /** Extra context, e.g. that the chart still shows the last good data. */
  note?: string;
}) {
  const { title, detail } = describeError(error);
  const isInput = "kind" in error && error.kind === "input";
  return (
    <Notice tone={isInput ? "warning" : "critical"} title={isInput && inputTitle ? inputTitle : title}>
      <p>
        {isInput ? detail : `Could not load ${what}. ${detail}`}
        {note ? ` ${note}` : ""}
      </p>
      {isInput ? null : (
        <div className="notice__actions">
          <button type="button" className="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </Notice>
  );
}

/**
 * Every fetch's states in one place: loading, waking, failed, empty, loaded.
 * Data already on screen stays there while a refresh is in flight or fails, and
 * the failure is shown above it rather than replacing it.
 */
export function Async<T>({
  state,
  what,
  height,
  isEmpty,
  emptyText,
  inputTitle,
  children,
}: {
  state: ApiState<T>;
  what: string;
  height?: number;
  isEmpty?: (data: T) => boolean;
  emptyText?: string;
  inputTitle?: string;
  children: (data: T) => ReactNode;
}) {
  const { data, error, waking, since, retry } = state;
  if (data !== null) {
    const empty = isEmpty?.(data) ?? false;
    return (
      <>
        {error ? (
          <FetchError
            error={error}
            what={what}
            onRetry={retry}
            inputTitle={inputTitle}
            note="What is shown is the last result that loaded."
          />
        ) : waking ? (
          <Waking since={since} onRetry={retry} />
        ) : null}
        {empty ? <p className="empty">{emptyText ?? `No data for ${what}.`}</p> : children(data)}
      </>
    );
  }
  if (error) return <FetchError error={error} what={what} onRetry={retry} inputTitle={inputTitle} />;
  if (waking) return <Waking since={since} onRetry={retry} />;
  return <Loading label={`Loading ${what}…`} height={height} />;
}

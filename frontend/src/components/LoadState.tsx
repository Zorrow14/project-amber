import { useEffect, useState, type ReactNode } from "react";

import { describeError } from "../api/client";
import type { ApiState } from "../hooks/useApi";
import { Banner, BannerActions } from "./Banner";

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

/**
 * A quiet skeleton in the shape of what is coming - a title line and a plot
 * block - instead of a spinner. The label is for screen readers.
 */
export function Loading({ label, height }: { label: string; height?: number }) {
  return (
    <div className="skeleton" role="status" data-loading style={height ? { minHeight: height } : undefined}>
      <span className="sr-only">{label}</span>
      <span className="skeleton__bar skeleton__bar--medium" aria-hidden="true" />
      <span className="skeleton__bar skeleton__bar--short" aria-hidden="true" />
      {height ? <span className="skeleton__block" aria-hidden="true" /> : null}
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
    <Banner tone="info" title="Waking the server - this can take up to a minute" role="status">
      <p>
        Amber's API runs on a free hosting tier that sleeps when nobody is using it. The first request
        after a pause starts it up again; this page keeps retrying on its own.
      </p>
      <BannerActions>
        <button type="button" className="button" onClick={onRetry}>
          Retry now
        </button>
        {since != null ? (
          <span className="muted num" aria-hidden="true">
            Waiting {elapsed} s
          </span>
        ) : null}
      </BannerActions>
    </Banner>
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
    <Banner tone={isInput ? "caution" : "critical"} title={isInput && inputTitle ? inputTitle : title}>
      <p>
        {isInput ? detail : `Could not load ${what}. ${detail}`}
        {note ? ` ${note}` : ""}
      </p>
      {isInput ? null : (
        <BannerActions>
          <button type="button" className="button" onClick={onRetry}>
            Retry
          </button>
        </BannerActions>
      )}
    </Banner>
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

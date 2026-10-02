import { useCallback, useEffect, useMemo, useState } from "react";

import { isTransient } from "../api/client";
import { useI18n } from "../i18n/context";
import { localize } from "../i18n/localize";

/** A request still in flight after this long is treated as a waking server. */
export const SLOW_AFTER_MS = 4_000;
/** How long transient failures are retried on their own before the error is shown. */
export const WAKE_BUDGET_MS = 90_000;
/** Back-off between automatic retries; the last value repeats. */
export const RETRY_DELAYS_MS = [2_000, 4_000, 8_000, 10_000] as const;

export interface ApiState<T> {
  /** The latest good data - kept on screen while a newer request is in flight. */
  data: T | null;
  /** The error for the current request, once retrying has stopped. */
  error: Error | null;
  /** True until the current request settles. */
  loading: boolean;
  /** The current request is slow or being retried: the server is probably waking. */
  waking: boolean;
  /** When the current request sequence started, for an elapsed-time display. */
  since: number | null;
  /** Start the request again, with a fresh retry budget. */
  retry: () => void;
}

interface Resolved<T> {
  token: string | null;
  data: T | null;
  error: Error | null;
}

interface Progress {
  token: string | null;
  waking: boolean;
  since: number;
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

/**
 * Run an API call whenever `key` changes, aborting the previous one.
 *
 * Transient failures (nothing answered, a timeout, a 502/503/504 gateway) are
 * retried with back-off for up to WAKE_BUDGET_MS - a free-tier host can take a
 * minute to wake - and `waking` says so meanwhile. Anything else, or a failure
 * past the budget, lands in `error`; `retry()` starts over.
 *
 * `data` comes back in the active UI language (`localize`): switching language
 * re-renders it from the twins already in hand, without a new request.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [nonce, setNonce] = useState(0);
  const [resolved, setResolved] = useState<Resolved<T>>({ token: null, data: null, error: null });
  const [progress, setProgress] = useState<Progress>({ token: null, waking: false, since: 0 });
  const token = `${key}#${nonce}`;

  useEffect(() => {
    const controller = new AbortController();
    const since = Date.now();
    let retryTimer: number | undefined;
    const markWaking = () => setProgress({ token, waking: true, since });
    const slowTimer = window.setTimeout(markWaking, SLOW_AFTER_MS);

    const attempt = (n: number) => {
      fetcher(controller.signal).then(
        (data) => setResolved({ token, data, error: null }),
        (error: unknown) => {
          if (controller.signal.aborted) return;
          const delay = RETRY_DELAYS_MS[Math.min(n, RETRY_DELAYS_MS.length - 1)] ?? RETRY_DELAYS_MS[0];
          if (isTransient(error) && Date.now() - since + delay <= WAKE_BUDGET_MS) {
            markWaking();
            retryTimer = window.setTimeout(() => attempt(n + 1), delay);
            return;
          }
          setResolved((previous) => ({ token, data: previous.data, error: toError(error) }));
        },
      );
    };
    attempt(0);

    return () => {
      controller.abort();
      window.clearTimeout(slowTimer);
      window.clearTimeout(retryTimer);
    };
    // The token is the dependency: callers encode everything the fetch depends on in `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  const { locale } = useI18n();
  const data = useMemo(() => localize(resolved.data, locale), [resolved.data, locale]);
  const current = resolved.token === token;
  const tracking = progress.token === token;
  return {
    data,
    error: current ? resolved.error : null,
    loading: !current,
    waking: !current && tracking && progress.waking,
    since: tracking ? progress.since : null,
    retry,
  };
}

/** `value`, but only after it has stopped changing for `delay` ms - for sliders. */
export function useDebounced<T>(value: T, delay = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

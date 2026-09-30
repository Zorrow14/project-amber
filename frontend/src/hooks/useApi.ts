import { useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

interface Resolved<T> {
  key: string | null;
  data: T | null;
  error: Error | null;
}

/**
 * Run an API call whenever `key` changes, aborting the previous one. The last
 * good data stays on screen while a new request is in flight; `loading` is
 * true until the response for the current key arrives.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [resolved, setResolved] = useState<Resolved<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    fetcher(controller.signal)
      .then((data) => setResolved({ key, data, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResolved((previous) => ({
          key,
          data: previous.data,
          error: error instanceof Error ? error : new Error(String(error)),
        }));
      });
    return () => controller.abort();
    // The key is the dependency: callers encode everything the fetch depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const current = resolved.key === key;
  return {
    data: resolved.data,
    error: current ? resolved.error : null,
    loading: !current,
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

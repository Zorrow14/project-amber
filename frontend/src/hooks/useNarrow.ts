import { useSyncExternalStore } from "react";

/** Phone-width breakpoint: below it, charts drop their end labels and side margins. */
export const NARROW_QUERY = "(max-width: 560px)";

function subscribe(onChange: () => void): () => void {
  const query = window.matchMedia?.(NARROW_QUERY);
  if (!query) return () => {};
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** Whether the viewport is phone-width, kept in step with resizes and rotation. */
export function useNarrow(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia?.(NARROW_QUERY).matches ?? false,
    () => false,
  );
}

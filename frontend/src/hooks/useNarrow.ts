import { useSyncExternalStore } from "react";

/** Phone-width breakpoint: below it, charts drop their end labels and side margins.
 * The same 560px as the phone media query in styles/components.css (CSS cannot
 * read a custom property inside a media query, so the two are kept in step). */
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

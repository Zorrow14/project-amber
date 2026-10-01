import { useEffect, useState } from "react";

export const VIEWS = ["overview", "history", "past", "counterfactual", "future"] as const;
export type View = (typeof VIEWS)[number];

/** The view a URL hash names; anything unknown is the overview. */
export function parseView(hash: string): View {
  const name = hash.replace(/^#\/?/, "");
  return (VIEWS as readonly string[]).includes(name) ? (name as View) : "overview";
}

/** The current view, kept in the URL hash so views are linkable - no storage. */
export function useHashRoute(): [View, (view: View) => void] {
  const [view, setView] = useState<View>(() => parseView(window.location.hash));
  useEffect(() => {
    const onChange = () => setView(parseView(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const navigate = (next: View) => {
    window.location.hash = `/${next}`;
  };
  return [view, navigate];
}

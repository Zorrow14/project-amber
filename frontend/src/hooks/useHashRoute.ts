import { useEffect, useState } from "react";

export const VIEWS = ["overview", "past", "counterfactual", "future"] as const;
export type View = (typeof VIEWS)[number];

function parse(hash: string): View {
  const name = hash.replace(/^#\/?/, "");
  return (VIEWS as readonly string[]).includes(name) ? (name as View) : "overview";
}

/** The current view, kept in the URL hash so views are linkable - no storage. */
export function useHashRoute(): [View, (view: View) => void] {
  const [view, setView] = useState<View>(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setView(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const navigate = (next: View) => {
    window.location.hash = `/${next}`;
  };
  return [view, navigate];
}

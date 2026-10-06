import { createContext, useContext, useEffect, type RefObject } from "react";

import { DEFAULT_VIEW, formatLocation, type Params, type View } from "../lib/url";

export interface Route {
  view: View;
  /** The open view's parameters as the URL gave them when it opened: a view's initial state. */
  params: Params;
  /** The element id the URL points at (`#sources`), or null. */
  anchor: string | null;
  /** Bumped by every navigation, so a target is scrolled to again even if the anchor is unchanged. */
  visit: number;
  /** Bumped by Back and Forward, which restore a view's state from the URL: key the view by it. */
  restored: number;
  /** Open a view: a new history entry. */
  navigate: (view: View, anchor?: string) => void;
  /** Record the open view's state in the URL, in place: all of its parameters, any left out or empty removed. */
  setParams: (params: Params) => void;
  /** The href for a view, in the current language, for links that also work opened in a new tab. */
  href: (view: View, anchor?: string) => string;
}

const STATIC: Route = {
  view: DEFAULT_VIEW,
  params: {},
  anchor: null,
  visit: 0,
  restored: 0,
  navigate: () => {},
  setParams: () => {},
  href: (view, anchor) => formatLocation({ view, anchor }),
};

/** The landing view with no state until a provider says otherwise, so components render in tests without one. */
export const RouteContext = createContext<Route>(STATIC);

export function useRoute(): Route {
  return useContext(RouteContext);
}

/** Scroll to and focus `ref` when the URL points at `id` - on arrival and on every later visit. */
export function useAnchorTarget(id: string, ref: RefObject<HTMLElement | null>) {
  const { anchor, visit } = useRoute();
  useEffect(() => {
    if (anchor !== id || !ref.current) return;
    ref.current.scrollIntoView({ block: "start" });
    ref.current.focus({ preventScroll: true });
  }, [anchor, id, ref, visit]);
}

/**
 * Keep the open view's state in the URL: call it every render with all of the
 * view's parameters, `undefined` for any at its default. Written in place, never
 * a new history entry.
 */
export function useUrlState(params: Params) {
  const { setParams } = useRoute();
  const key = JSON.stringify(params);
  useEffect(() => {
    setParams(JSON.parse(key) as Params);
  }, [key, setParams]);
}

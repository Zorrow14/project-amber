import { useCallback, useEffect, useMemo, useRef, useState, type AnchorHTMLAttributes, type ReactNode } from "react";

import { useI18n } from "../i18n/context";
import { preferredLocale } from "../i18n/detect";
import { formatLocation, parseLocation, VIEW_PARAMS, type AppLocation, type Params, type View } from "../lib/url";
import { RouteContext, useRoute, type Route } from "./routeContext";

function currentLocation(): AppLocation {
  return parseLocation(window.location.search, window.location.hash);
}

/**
 * The URL as the app's shareable state: the view, its controls and the language.
 * Opening a view pushes a history entry; changing a control rewrites the
 * current one (history.replaceState), so Back leaves the view rather than
 * undoing slider steps. Nothing is stored anywhere else.
 */
export function RouteProvider({ children }: { children: ReactNode }) {
  const { locale, pending } = useI18n();
  const [state, setState] = useState(() => ({ location: currentLocation(), visit: 0, restored: 0 }));
  // What the URL holds now, including parameters views wrote since they opened.
  const live = useRef<AppLocation>(state.location);

  const write = useCallback((mode: "push" | "replace") => {
    const href = formatLocation(live.current, window.location.pathname);
    const now = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (mode === "push") window.history.pushState(null, "", href);
    else if (href !== now) window.history.replaceState(window.history.state, "", href);
  }, []);

  // The language goes in the URL unless it is English and the browser would pick English anyway.
  const shown = pending ?? locale;
  const lang = shown !== "en" || preferredLocale() !== "en" ? shown : null;
  useEffect(() => {
    live.current = { ...live.current, lang };
    write("replace");
  }, [lang, write]);

  useEffect(() => {
    const onPop = () => {
      live.current = currentLocation();
      write("replace"); // a legacy `#/view` link becomes `?view=`
      setState((s) => ({ location: live.current, visit: s.visit + 1, restored: s.restored + 1 }));
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [write]);

  const navigate = useCallback(
    (view: View, anchor?: string) => {
      if (view === live.current.view && !anchor) return;
      // A new view starts clean: its own defaults, and none of the landing URL's foreign parameters.
      live.current = { ...live.current, view, params: {}, anchor: anchor ?? null, extra: [] };
      write("push");
      setState((s) => ({ ...s, location: live.current, visit: s.visit + 1 }));
    },
    [write],
  );

  const setParams = useCallback(
    (params: Params) => {
      const own = new Set<string>(VIEW_PARAMS[live.current.view]);
      const next = Object.fromEntries(
        Object.entries(params).filter(([key, value]) => own.has(key) && Boolean(value)),
      ) as Params;
      live.current = { ...live.current, params: next, anchor: null };
      write("replace");
    },
    [write],
  );

  const href = useCallback(
    (view: View, anchor?: string) => formatLocation({ view, anchor, lang }, window.location.pathname),
    [lang],
  );

  const value = useMemo<Route>(
    () => ({
      view: state.location.view,
      params: state.location.params,
      anchor: state.location.anchor,
      visit: state.visit,
      restored: state.restored,
      navigate,
      setParams,
      href,
    }),
    [state, navigate, setParams, href],
  );
  return <RouteContext.Provider value={value}>{children}</RouteContext.Provider>;
}

/**
 * A link to a view. A plain click opens it in place; a modified click (new tab,
 * new window) follows the href, which carries the language.
 */
export function Link({
  view,
  anchor,
  onClick,
  children,
  ...rest
}: { view: View; anchor?: string; children: ReactNode } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  const route = useRoute();
  return (
    <a
      {...rest}
      href={route.href(view, anchor)}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        event.preventDefault();
        route.navigate(view, anchor);
      }}
    >
      {children}
    </a>
  );
}

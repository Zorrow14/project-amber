/**
 * The app's state in its URL, so a link reproduces what the reader saw. Pure
 * functions only: `context/route.tsx` reads and writes `window.location`.
 *
 *   ?view=future&scenario=reform_push&levers=education_spend:1.5&lang=my
 *
 * - `view` names the view; it is left out for the landing view.
 * - Each view's own parameters (VIEW_PARAMS) are written only while that view
 *   is open, and only when they differ from their defaults.
 * - Number maps are `name:value` pairs joined by commas, left unescaped.
 * - `lang` is the UI language, left out when the page is in English and the
 *   browser would have chosen English anyway.
 *
 * Values are checked against /meta by the view that reads them, not here.
 */
import { LOCALES, type Locale } from "../i18n/catalog";

export const VIEWS = ["about", "overview", "history", "past", "counterfactual", "future"] as const;
export type View = (typeof VIEWS)[number];

/** The Sources & citations section's id: footer and chart-source links point at `/#sources`. */
export const SOURCES_ANCHOR = "sources";

export function isView(name: unknown): name is View {
  return (VIEWS as readonly unknown[]).includes(name);
}

const configured: unknown = import.meta.env.VITE_DEFAULT_VIEW;

/** The landing view: About, unless the build sets VITE_DEFAULT_VIEW (e.g. "overview"). */
export const DEFAULT_VIEW: View = isView(configured) ? configured : "about";

/** Each view's own parameters, in the order they are written. */
export const VIEW_PARAMS = {
  about: [],
  overview: [],
  history: ["comparator"],
  past: ["weights"],
  counterfactual: [],
  future: ["scenario", "levers", "series"],
} as const satisfies Record<View, readonly string[]>;

export type Param = (typeof VIEW_PARAMS)[View][number];
export type Params = Partial<Record<Param, string>>;

const ALL_PARAMS = new Set<string>(Object.values(VIEW_PARAMS).flat());
const OWN_KEYS = new Set<string>(["view", "lang", ...ALL_PARAMS]);

export interface AppLocation {
  view: View;
  /** The language the URL asks for, or null to follow the browser. */
  lang: Locale | null;
  /** The view's own parameters, raw. */
  params: Params;
  /** An element id to scroll to (`#sources`), or null. */
  anchor: string | null;
  /** Query parameters that are not Amber's (utm tags and the like), kept as they came. */
  extra: [string, string][];
}

/**
 * Where a URL points. A legacy hash route (`#/past`, from before the state moved
 * to the query) still names the view, so old links keep working.
 */
export function parseLocation(search: string, hash = ""): AppLocation {
  const query = new URLSearchParams(search);
  const legacy = /^#\/(\w+)/.exec(hash)?.[1];
  const named = query.get("view");
  const view = isView(named) ? named : isView(legacy) ? legacy : DEFAULT_VIEW;
  const lang = query.get("lang");
  const params: Params = {};
  for (const key of VIEW_PARAMS[view]) {
    const value = query.get(key);
    if (value) params[key] = value;
  }
  const anchor = hash.startsWith("#") && !hash.startsWith("#/") && hash.length > 1 ? decodeURIComponent(hash.slice(1)) : null;
  return {
    view,
    lang: (LOCALES as readonly (string | null)[]).includes(lang) ? (lang as Locale) : null,
    params,
    anchor,
    extra: [...query.entries()].filter(([key]) => !OWN_KEYS.has(key)),
  };
}

// `,` and `:` are legal in a query and read better than %2C and %3A.
const encode = (value: string) => encodeURIComponent(value).replace(/%2C/gi, ",").replace(/%3A/gi, ":");

/** The path, query and hash for a location - what goes in an `href` and in `history`. */
export function formatLocation(location: Partial<AppLocation> & { view: View }, pathname = "/"): string {
  const parts: string[] = [];
  if (location.view !== DEFAULT_VIEW) parts.push(`view=${location.view}`);
  for (const key of VIEW_PARAMS[location.view]) {
    const value = location.params?.[key];
    if (value) parts.push(`${key}=${encode(value)}`);
  }
  if (location.lang) parts.push(`lang=${location.lang}`);
  for (const [key, value] of location.extra ?? []) parts.push(`${encode(key)}=${encode(value)}`);
  const query = parts.length > 0 ? `?${parts.join("&")}` : "";
  return `${pathname}${query}${location.anchor ? `#${encodeURIComponent(location.anchor)}` : ""}`;
}

/** `{a: 1, b: 0.5}` -> `"a:1,b:0.5"`, at most `digits` decimals and no trailing zeros. */
export function formatNumbers(values: Record<string, number>, digits = 2): string {
  return Object.entries(values)
    .map(([name, value]) => `${name}:${Number(value.toFixed(digits))}`)
    .join(",");
}

/** `"a:1,b:0.5"` -> `{a: 1, b: 0.5}`; a malformed pair is dropped, not guessed at. */
export function parseNumbers(text: string | undefined): Record<string, number> {
  const values: Record<string, number> = {};
  for (const pair of (text ?? "").split(",")) {
    const match = /^([\w.-]+):(-?\d+(?:\.\d+)?)$/.exec(pair.trim());
    if (match?.[1] && match[2]) values[match[1]] = Number(match[2]);
  }
  return values;
}

/** Clamp to [min, max] and snap to the nearest step from min, so a hand-edited URL stays valid. */
export function snap(value: number, min: number, max: number, step?: number): number {
  const clamped = Math.min(max, Math.max(min, value));
  if (!step) return clamped;
  const snapped = min + Math.round((clamped - min) / step) * step;
  return Number(Math.min(max, snapped).toFixed(6));
}

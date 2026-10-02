import type { Locale } from "./catalog";

/**
 * Every display string the API sends has a twin beside it: `name` and
 * `name_i18n: {en, my}`, `notes` and `notes_i18n: [{en, my}, ...]`, `framing`
 * and `framing_i18n: {field: {en, my}}`. `localize` returns the payload with each
 * display field replaced by its twin in `locale`, so components read `c.name` or
 * `meta.framing.coverage` as before and get the active language - no view can
 * show an English series name in Burmese mode by forgetting a lookup.
 *
 * English is the payload as sent. Results are cached per object and locale, so
 * the same data keeps its identity across renders.
 */

const SUFFIX = "_i18n";
const cache = new WeakMap<object, Map<Locale, unknown>>();

function isLocalized(value: unknown): value is Record<Locale, string> {
  return value != null && typeof value === "object" && !Array.isArray(value) && "en" in value && "my" in value;
}

/** A twin's value in `locale`: a string, a list of strings, or an object of them (framing). */
function choose(twin: unknown, locale: Locale): unknown {
  if (twin == null) return twin;
  if (Array.isArray(twin)) return twin.map((item) => choose(item, locale));
  if (isLocalized(twin)) return twin[locale] ?? twin.en;
  if (typeof twin === "object") {
    return Object.fromEntries(Object.entries(twin).map(([key, value]) => [key, choose(value, locale)]));
  }
  return twin;
}

function walk(node: unknown, locale: Locale): unknown {
  if (node == null || typeof node !== "object") return node;
  const cached = cache.get(node)?.get(locale);
  if (cached !== undefined) return cached;

  let result: unknown;
  if (Array.isArray(node)) {
    // Numeric series are most of the bytes; leave arrays of plain values as they are.
    result = node.some((item) => item != null && typeof item === "object") ? node.map((item) => walk(item, locale)) : node;
  } else {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(node)) out[key] = walk(value, locale);
    for (const [key, value] of Object.entries(node)) {
      if (key.endsWith(SUFFIX) && key.slice(0, -SUFFIX.length) in node) {
        out[key.slice(0, -SUFFIX.length)] = choose(value, locale);
      }
    }
    result = out;
  }
  const byLocale = cache.get(node) ?? new Map<Locale, unknown>();
  byLocale.set(locale, result);
  cache.set(node, byLocale);
  return result;
}

/** `data` with every display field in `locale` (see the module doc). */
export function localize<T>(data: T, locale: Locale): T {
  return locale === "en" ? data : (walk(data, locale) as T);
}

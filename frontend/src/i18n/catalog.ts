/**
 * The UI's two message catalogs and how to read them.
 *
 * `en.json` is the source of truth: its shape types every key, so tsc rejects a
 * key that does not exist, and `my.json` must have exactly the same keys and
 * placeholders (`i18n.test.ts`). English ships with the app; Burmese is its own
 * chunk, fetched only when it is chosen, so an English reader downloads none of it.
 *
 * Numerals stay Western in both languages - "2021", never "၂၀၂၁" - so
 * placeholders are filled with the app's own formatters (pinned to en-US) and
 * nothing here formats a number.
 */
import en from "./locales/en.json";

export const LOCALES = ["en", "my"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Each language's name for itself, shown on the toggle in its own script - never translated. */
export const ENDONYMS: Record<Locale, { short: string; full: string }> = {
  en: { short: "EN", full: "English" },
  my: { short: "မြန်မာ", full: "မြန်မာဘာသာ" },
};

export type Messages = typeof en;

type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];

/** Every message key, as a dotted path: `"nav.overview"`, `"honesty.scenarioBadge"`. */
export type MessageKey = Leaves<Messages>;
export type Vars = Record<string, string | number>;

export const ENGLISH: Messages = en;

const loading = new Map<Locale, Promise<Messages>>();

/** A locale's catalog, fetched once. */
export function loadCatalog(locale: Locale): Promise<Messages> {
  if (locale === "en") return Promise.resolve(en);
  let pending = loading.get(locale);
  if (!pending) {
    // Assigning to Messages is the compile-time half of the parity check: a
    // Burmese catalog missing any English key does not type-check.
    pending = import("./locales/my.json").then((module) => {
      const catalog: Messages = module.default;
      return catalog;
    });
    pending.catch(() => loading.delete(locale));
    loading.set(locale, pending);
  }
  return pending;
}

/** The raw template at `key`, or undefined. */
export function lookup(messages: Messages, key: string): string | undefined {
  let node: unknown = messages;
  for (const part of key.split(".")) {
    if (node == null || typeof node !== "object") return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

const PLACEHOLDER = /\{(\w+)\}/g;

/** The names of a template's `{placeholders}`. */
export function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((match) => match[1] ?? "");
}

/** `{name}` placeholders filled from `vars`; one with no value is left visible, never blanked. */
export function interpolate(template: string, vars: Vars = {}): string {
  return template.replace(PLACEHOLDER, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

/** A key in `messages`, falling back to English if a catalog ever lacks it. */
export function translate(messages: Messages, key: MessageKey, vars?: Vars): string {
  return interpolate(lookup(messages, key) ?? lookup(en, key) ?? key, vars);
}

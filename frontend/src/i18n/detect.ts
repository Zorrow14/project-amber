import { DEFAULT_LOCALE, LOCALES, type Locale } from "./catalog";

/**
 * The reader's first supported language, in the browser's order of preference
 * (`navigator.languages` is the Accept-Language list): `my-MM` and `my` pick
 * Burmese, `en-*` English; anything else falls back to English.
 */
export function preferredLocale(languages: readonly string[] = browserLanguages()): Locale {
  for (const tag of languages) {
    const base = tag.toLowerCase().split("-")[0];
    const match = LOCALES.find((locale) => locale === base);
    if (match) return match;
  }
  return DEFAULT_LOCALE;
}

function browserLanguages(): readonly string[] {
  if (typeof navigator === "undefined") return [];
  return navigator.languages?.length ? navigator.languages : [navigator.language];
}

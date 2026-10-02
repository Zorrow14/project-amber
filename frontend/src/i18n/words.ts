import type { I18n } from "./context";

/**
 * The few things that are grammar rather than vocabulary: ordinals, lists and
 * the ratio sign. Digits stay Western in both languages; only the words around
 * them change ("7th of 7" / "7 ခုအနက် အဆင့် 7").
 */

/** "1st", "2nd", ... in English (CLDR ordinal rules); "အဆင့် 1" in Burmese. */
export function ordinal(i18n: I18n, n: number): string {
  const category = new Intl.PluralRules(i18n.locale, { type: "ordinal" }).select(n);
  return i18n.t(`meta.ordinal.${category}`, { n });
}

/** "7th of 7". */
export function rankOf(i18n: I18n, rank: number, n: number): string {
  return i18n.t("meta.rankOf", { ordinal: ordinal(i18n, rank), n });
}

/** Items joined with the language's list separator ("a, b, c" / "a၊ b၊ c"). */
export function list(i18n: I18n, items: string[]): string {
  return items.join(i18n.t("meta.listSeparator"));
}

/** Items joined with "and" ("a and b" / "a နှင့် b"). */
export function listAnd(i18n: I18n, items: string[]): string {
  return items.join(i18n.t("meta.listAnd"));
}

/** A ratio to the actual level: "1.25×". */
export function ratio(i18n: I18n, value: number): string {
  return i18n.t("meta.ratio", { value: value.toFixed(2) });
}

/** A reliability flag as a word. */
export function reliabilityWord(i18n: I18n, reliability: string): string {
  return reliability === "low" ? i18n.t("meta.reliabilityLow") : i18n.t("meta.reliabilityStandard");
}

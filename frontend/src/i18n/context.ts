import { createContext, createElement, Fragment, useContext, type ReactNode } from "react";

import type { Localized } from "../api/types";
import { ENGLISH, lookup, translate, type Locale, type MessageKey, type Messages, type Vars } from "./catalog";

export interface I18n {
  /** The language on screen - its catalog is loaded. */
  locale: Locale;
  /** A language that was chosen but whose catalog is still loading, else null. */
  pending: Locale | null;
  setLocale: (locale: Locale) => void;
  /** A message in the active language, `{placeholders}` filled. */
  t: (key: MessageKey, vars?: Vars) => string;
  /** A message whose placeholders are elements - a link, a `<code>` - rather than text. */
  tNodes: (key: MessageKey, nodes: Record<string, ReactNode>) => ReactNode;
  /** One of the API's `{en, my}` twins in the active language. */
  pick: (text: Localized | null | undefined) => string;
  /** Whether this catalog still has translations flagged for human review. */
  reviewPending: boolean;
  /** Whether this message's translation is still a draft awaiting human review. */
  needsReview: (key: MessageKey) => boolean;
}

/** A catalog's review flags: `_review` maps a key to "human-verify" until a Burmese speaker signs it off. */
export function pendingReviews(messages: Messages): string[] {
  const flags = (messages as Messages & { _review?: Record<string, string> })._review ?? {};
  return Object.entries(flags)
    .filter(([, status]) => status === "human-verify")
    .map(([key]) => key);
}

/** Split a template on its placeholders and drop elements in. */
export function interpolateNodes(template: string, nodes: Record<string, ReactNode>): ReactNode {
  const parts = template.split(/\{(\w+)\}/g);
  return parts.map((part, i) => createElement(Fragment, { key: i }, i % 2 === 1 ? (nodes[part] ?? `{${part}}`) : part));
}

/** The context's value for one language. */
export function i18nFor(
  locale: Locale,
  messages: Messages,
  options: { pending?: Locale | null; setLocale?: (locale: Locale) => void } = {},
): I18n {
  const flagged = new Set(pendingReviews(messages));
  return {
    locale,
    pending: options.pending ?? null,
    setLocale: options.setLocale ?? (() => {}),
    t: (key, vars) => translate(messages, key, vars),
    tNodes: (key, nodes) => interpolateNodes(lookup(messages, key) ?? lookup(ENGLISH, key) ?? key, nodes),
    pick: (text) => (text ? (text[locale] ?? text.en) : ""),
    reviewPending: flagged.size > 0,
    needsReview: (key) => flagged.has(key),
  };
}

/** English until a provider says otherwise, so a component renders in a test without one. */
export const I18nContext = createContext<I18n>(i18nFor("en", ENGLISH));

export function useI18n(): I18n {
  return useContext(I18nContext);
}

/** The translate function for the active language. */
export function useT(): I18n["t"] {
  return useContext(I18nContext).t;
}

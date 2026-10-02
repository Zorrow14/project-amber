import { useCallback, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from "react";

import { ENGLISH, loadCatalog, translate, type Locale, type Messages } from "./catalog";
import { I18nContext, i18nFor } from "./context";
import { preferredLocale } from "./detect";

/**
 * The UI language, held in memory for the session (no storage, by project rule).
 * It starts from the browser's preference and falls back to English; the header
 * toggle switches it. A chosen language goes on screen only once its catalog has
 * loaded, and `<html lang>` always names the language actually shown - for
 * screen readers, and so Burmese gets its own font stack and line height.
 */
export function I18nProvider({
  children,
  initialLocale,
  catalogs,
}: {
  children: ReactNode;
  /** Defaults to the browser's preference. */
  initialLocale?: Locale;
  /** Catalogs already in hand (tests); others are fetched on demand. */
  catalogs?: Partial<Record<Locale, Messages>>;
}) {
  const [requested, setRequested] = useState<Locale>(() => initialLocale ?? preferredLocale());
  const [loaded, setLoaded] = useState<Partial<Record<Locale, Messages>>>(() => ({ en: ENGLISH, ...catalogs }));
  const messages = loaded[requested];
  const locale: Locale = messages ? requested : "en";

  useEffect(() => {
    if (loaded[requested]) return;
    let live = true;
    loadCatalog(requested).then(
      (catalog) => live && setLoaded((current) => ({ ...current, [requested]: catalog })),
      // A catalog that cannot load leaves the page in English rather than blank.
      () => live && setRequested("en"),
    );
    return () => {
      live = false;
    };
  }, [requested, loaded]);

  // Before paint, so the Burmese line height and font stack apply to the first frame.
  useLayoutEffect(() => {
    document.documentElement.lang = locale;
    document.title = translate(loaded[locale] ?? ENGLISH, "app.title");
  }, [locale, loaded]);

  const setLocale = useCallback((next: Locale) => setRequested(next), []);
  const value = useMemo(
    () =>
      i18nFor(locale, loaded[locale] ?? ENGLISH, {
        pending: requested === locale ? null : requested,
        setLocale,
      }),
    [locale, loaded, requested, setLocale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

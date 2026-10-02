import { useEffect, useRef, type ReactNode } from "react";

import type { View } from "../hooks/useHashRoute";
import { ENDONYMS, LOCALES } from "../i18n/catalog";
import { useI18n } from "../i18n/context";
import { useTheme } from "../theme/themeContext";
import { Icon } from "./Icon";

/**
 * The page frame: a quiet sticky top bar (brand, views, language and theme
 * toggles), the main column and a footer. On a view change focus moves to the
 * new content, so keyboard and screen-reader users land on it.
 */
export function AppShell({
  views,
  labels,
  current,
  footer,
  children,
}: {
  views: readonly View[];
  labels: Record<View, string>;
  current: View;
  footer: ReactNode;
  children: ReactNode;
}) {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
    window.scrollTo({ top: 0 });
  }, [current]);

  const switchTheme = theme === "light" ? t("app.themeToDark") : t("app.themeToLight");
  return (
    <div className="shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          main.current?.focus();
        }}
      >
        {t("app.skip")}
      </a>
      <header className="shell-header">
        <div className="shell-header__inner">
          <a className="brand" href="#/overview" aria-label={t("app.brandLabel")}>
            <span className="brand__mark" aria-hidden="true" />
            {t("app.brand")}
            <span className="brand__descriptor">{t("app.descriptor")}</span>
          </a>
          <nav className="nav" aria-label={t("app.views")}>
            <ul className="nav__list">
              {views.map((name) => (
                <li key={name}>
                  <a href={`#/${name}`} className="nav__link" aria-current={name === current ? "page" : undefined}>
                    {labels[name]}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="shell-header__tools">
            <LanguageToggle />
            <button type="button" className="icon-button" onClick={toggle} aria-label={switchTheme} title={switchTheme}>
              <Icon name={theme === "light" ? "moon" : "sun"} />
            </button>
          </div>
        </div>
      </header>

      <main className="shell-main" id="main" ref={main} tabIndex={-1} aria-label={labels[current]}>
        {children}
      </main>

      <footer className="shell-footer">
        <div className="shell-footer__inner">{footer}</div>
      </footer>
    </div>
  );
}

/**
 * EN / မြန်မာ: two buttons, the active one pressed. Each language is named in
 * its own script and tagged with its `lang`, so a screen reader pronounces it
 * correctly whatever the page language. Native buttons, so Tab, Enter and Space work.
 */
export function LanguageToggle() {
  const { locale, pending, setLocale, t } = useI18n();
  return (
    <div className="language-toggle" role="group" aria-label={t("app.language")} aria-busy={pending ? true : undefined}>
      {LOCALES.map((option) => (
        <button
          key={option}
          type="button"
          className="language-toggle__option"
          lang={option}
          aria-pressed={option === locale}
          aria-label={ENDONYMS[option].full}
          title={pending === option ? t("app.languageLoading", { language: ENDONYMS[option].full }) : ENDONYMS[option].full}
          onClick={() => setLocale(option)}
        >
          {ENDONYMS[option].short}
        </button>
      ))}
    </div>
  );
}

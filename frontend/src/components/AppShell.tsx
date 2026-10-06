import { useEffect, useRef, useState, type ReactNode } from "react";

import { Link } from "../context/route";
import { useRoute } from "../context/routeContext";
import { ENDONYMS, LOCALES } from "../i18n/catalog";
import { useI18n } from "../i18n/context";
import { useTheme } from "../theme/themeContext";
import { DEFAULT_VIEW, type View } from "../lib/url";
import { Icon } from "./Icon";

/**
 * The page frame: a quiet sticky top bar (brand, views, copy-link, language and
 * theme toggles), the main column and a footer. On a view change focus moves to
 * the new content, so keyboard and screen-reader users land on it - or to the
 * section the link pointed at.
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
  const { anchor, visit } = useRoute();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (anchor) return; // the section it names scrolls itself into view (useAnchorTarget)
    main.current?.focus();
    window.scrollTo({ top: 0 });
  }, [current, anchor, visit]);

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
          <Link className="brand" view={DEFAULT_VIEW} aria-label={t("app.brandLabel")}>
            <span className="brand__mark" aria-hidden="true" />
            {t("app.brand")}
            <span className="brand__descriptor">{t("app.descriptor")}</span>
          </Link>
          <nav className="nav" aria-label={t("app.views")}>
            <ul className="nav__list">
              {views.map((name) => (
                <li key={name}>
                  <Link view={name} className="nav__link" aria-current={name === current ? "page" : undefined}>
                    {labels[name]}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="shell-header__tools">
            <CopyLink />
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

/**
 * Copies the page's address, which holds the view, its controls and the
 * language, so the link reproduces what the reader sees. The result is
 * announced, and shown for a moment beside the button.
 */
export function CopyLink() {
  const { t } = useI18n();
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => {
    if (status === "idle") return;
    const timer = window.setTimeout(() => setStatus("idle"), 3000);
    return () => window.clearTimeout(timer);
  }, [status]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setStatus("copied");
    } catch {
      // No clipboard (an insecure origin, a denied permission): the address bar still has it.
      setStatus("failed");
    }
  };
  const message = status === "copied" ? t("share.copied") : status === "failed" ? t("share.failed") : "";
  return (
    <span className="copy-link">
      <button type="button" className="icon-button" onClick={copy} aria-label={t("share.copy")} title={t("share.copy")}>
        <Icon name={status === "copied" ? "check" : "link"} />
      </button>
      {/* Always in the tree, so the live region exists before its text arrives. */}
      <span className="copy-link__status" role="status">
        {message}
      </span>
    </span>
  );
}

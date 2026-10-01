import { useEffect, useRef, type ReactNode } from "react";

import type { View } from "../hooks/useHashRoute";
import { useTheme } from "../theme/themeContext";
import { Icon } from "./Icon";

/**
 * The page frame: a quiet sticky top bar (brand, views, theme toggle), the main
 * column and a footer. On a view change focus moves to the new content, so
 * keyboard and screen-reader users land on it.
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

  const next = theme === "light" ? "dark" : "light";
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
        Skip to content
      </a>
      <header className="shell-header">
        <div className="shell-header__inner">
          <a className="brand" href="#/overview" aria-label="Amber - overview">
            <span className="brand__mark" aria-hidden="true" />
            Amber
            <span className="brand__descriptor">Myanmar development</span>
          </a>
          <nav className="nav" aria-label="Views">
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
          <button
            type="button"
            className="icon-button"
            onClick={toggle}
            aria-label={`Switch to ${next} theme`}
            title={`Switch to ${next} theme`}
          >
            <Icon name={theme === "light" ? "moon" : "sun"} />
          </button>
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

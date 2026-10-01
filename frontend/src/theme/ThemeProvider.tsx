import { useCallback, useMemo, useState, type ReactNode } from "react";

import { applyTheme, ThemeContext, type ThemeName } from "./themeContext";

/**
 * Light by default; the header toggle switches to dark for the session. The
 * attribute is set before the state update, so charts that read their colors
 * from CSS during render already see the new tokens.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>(() => {
    applyTheme("light");
    return "light";
  });
  const toggle = useCallback(() => {
    setTheme((current) => {
      const next: ThemeName = current === "light" ? "dark" : "light";
      applyTheme(next);
      return next;
    });
  }, []);
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

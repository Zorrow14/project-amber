import { createContext, useContext } from "react";

export type ThemeName = "light" | "dark";

export interface ThemeState {
  theme: ThemeName;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeState>({ theme: "light", toggle: () => {} });

/** The active color theme and its toggle. Held in memory only - no storage. */
export function useTheme(): ThemeState {
  return useContext(ThemeContext);
}

/** Apply a theme to the document; tokens.css keys every color off this attribute. */
export function applyTheme(theme: ThemeName): void {
  document.documentElement.dataset.theme = theme;
}

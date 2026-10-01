import { useMemo } from "react";

import { applyTheme, useTheme, type ThemeName } from "../theme/themeContext";

/**
 * Chart colors, read from the tokens in styles/tokens.css so light and dark are
 * defined in one place. The treated country always takes the hero color and the
 * donors take data slots 1-6 in /meta order - a fixed map, so every chart colors
 * a country identically and a filter never repaints the survivors.
 */
export interface ChartTheme {
  hero: string;
  data: string[];
  text1: string;
  text2: string;
  text3: string;
  neutral: string;
  muted: string;
  faint: string;
  grid: string;
  axis: string;
  tick: string;
  reference: string;
  context: string;
  surface: string;
  caution: string;
  bandOpacity: number;
}

const DATA_SLOTS = 6;

// Light-theme values for jsdom and first paint, before stylesheets resolve. They
// mirror tokens.css; the live values always come from CSS.
const FALLBACK: ChartTheme = {
  hero: "#1d4ed8",
  data: ["#0d9e8d", "#a46ad8", "#679a29", "#d15a94", "#3a8ec0", "#a08332"],
  text1: "#0a0a0a",
  text2: "#525252",
  text3: "#6b6b6b",
  neutral: "#525252",
  muted: "#8f8f8f",
  faint: "#c4c4c4",
  grid: "#f0f0f0",
  axis: "#d4d4d4",
  tick: "#6b6b6b",
  reference: "#8a8a8a",
  context: "#f5f5f5",
  surface: "#ffffff",
  caution: "#7c5e10",
  bandOpacity: 0.14,
};

/** Read the tokens for `theme`, making sure the document is showing that theme first. */
function read(theme: ThemeName): ChartTheme {
  if (typeof window === "undefined") return FALLBACK;
  if (document.documentElement.dataset.theme !== theme) applyTheme(theme);
  const style = window.getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    hero: get("--data-hero", FALLBACK.hero),
    data: Array.from({ length: DATA_SLOTS }, (_, i) => get(`--data-${i + 1}`, FALLBACK.data[i] ?? FALLBACK.hero)),
    text1: get("--text-1", FALLBACK.text1),
    text2: get("--text-2", FALLBACK.text2),
    text3: get("--text-3", FALLBACK.text3),
    neutral: get("--chart-neutral", FALLBACK.neutral),
    muted: get("--chart-muted", FALLBACK.muted),
    faint: get("--chart-faint", FALLBACK.faint),
    grid: get("--chart-grid", FALLBACK.grid),
    axis: get("--chart-axis", FALLBACK.axis),
    tick: get("--chart-tick", FALLBACK.tick),
    reference: get("--chart-reference", FALLBACK.reference),
    context: get("--chart-context", FALLBACK.context),
    surface: get("--surface", FALLBACK.surface),
    caution: get("--caution-fg", FALLBACK.caution),
    bandOpacity: Number(get("--chart-band-opacity", String(FALLBACK.bandOpacity))) || FALLBACK.bandOpacity,
  };
}

/** The current chart theme, re-read whenever the theme toggles. */
export function useChartTheme(): ChartTheme {
  const { theme } = useTheme();
  return useMemo(() => read(theme), [theme]);
}

/** Every country's color: the treated country is the hero, donors take slots in order. */
export function countryColors(
  theme: ChartTheme,
  countries: { iso3: string; treated: boolean }[],
): Map<string, string> {
  const colors = new Map<string, string>();
  let slot = 0;
  for (const country of countries) {
    if (country.treated) colors.set(country.iso3, theme.hero);
    else colors.set(country.iso3, theme.data[slot++ % theme.data.length] ?? theme.neutral);
  }
  return colors;
}

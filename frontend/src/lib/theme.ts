import { useEffect, useState } from "react";

/**
 * Chart colors, read from the CSS custom properties in styles.css so light and
 * dark mode are defined in one place. Categorical slots are assigned in fixed
 * order by entity (see seriesColor), never cycled or re-ranked.
 */
export interface ChartTheme {
  series: string[];
  ink: string;
  inkSecondary: string;
  muted: string;
  grid: string;
  axis: string;
  surface: string;
  context: string;
  placebo: string;
  placeboFaint: string;
}

const SLOT_COUNT = 8;

// Light-mode fallbacks: what jsdom and first paint see before styles resolve.
const FALLBACK: ChartTheme = {
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  ink: "#0b0b0b",
  inkSecondary: "#52514e",
  muted: "#6f6d68",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  surface: "#fcfcfb",
  context: "#f0efec",
  placebo: "#8a8984",
  placeboFaint: "#b4b3ab",
};

function read(): ChartTheme {
  if (typeof window === "undefined") return FALLBACK;
  const style = window.getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    series: Array.from({ length: SLOT_COUNT }, (_, i) =>
      get(`--series-${i + 1}`, FALLBACK.series[i] ?? FALLBACK.ink),
    ),
    ink: get("--text-primary", FALLBACK.ink),
    inkSecondary: get("--text-secondary", FALLBACK.inkSecondary),
    muted: get("--text-muted", FALLBACK.muted),
    grid: get("--grid", FALLBACK.grid),
    axis: get("--axis", FALLBACK.axis),
    surface: get("--surface-1", FALLBACK.surface),
    context: get("--context", FALLBACK.context),
    placebo: get("--placebo", FALLBACK.placebo),
    placeboFaint: get("--placebo-faint", FALLBACK.placeboFaint),
  };
}

/** The current chart theme, re-read when the OS switches light/dark. */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(read);
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    const update = () => setTheme(read());
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return theme;
}

/** The slot for the i-th entity in its meta order - stable across filters. */
export function seriesColor(theme: ChartTheme, index: number): string {
  return theme.series[index % theme.series.length] ?? theme.ink;
}

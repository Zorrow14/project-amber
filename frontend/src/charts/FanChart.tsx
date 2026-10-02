import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer } from "recharts";

import type { Nullable } from "../api/types";
import { useT } from "../i18n/context";
import { CHART } from "../lib/chartTokens";
import { drawProps, MOTION, useMotion } from "../lib/motion";
import { lastPoint } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import {
  covidBands,
  grid,
  hollowWhenPartial,
  projectionLine,
  tooltip,
  treatmentLine,
  useChartLayout,
  valueAxis,
  yearAxis,
} from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";

export interface FanSeries {
  years: number[];
  p10: Nullable<number>[];
  p50: Nullable<number>[];
  p90: Nullable<number>[];
  /** First year drawn: where the scenario leaves history. */
  from: number;
  label: string;
}

/**
 * A scenario's p10–p90 band and median against history. Real Myanmar (history)
 * is the hero; what is modeled is ink: a crisp median over a soft band, the
 * baseline scenario dotted, the phase 3 synthetic control dashed. Every line has
 * its own pattern and an end label, so none is told apart by color alone.
 */
export function FanChart({
  series,
  baseline,
  history,
  synthetic,
  treatmentYear,
  projectionStart,
  covidYears,
  format,
  cursorYear = null,
}: {
  series: FanSeries;
  baseline?: { label: string; p50: Nullable<number>[] } | null;
  history?: { values: Nullable<number>[]; coverage?: Nullable<number>[]; years: number[] } | null;
  synthetic?: { years: number[]; values: Nullable<number>[] } | null;
  treatmentYear: number;
  projectionStart: number;
  covidYears: number[];
  format: (value: number) => string;
  /** The year the development player is on; a thin cursor marks it. */
  cursorYear?: number | null;
}) {
  const theme = useChartTheme();
  const t = useT();
  const motion = useMotion();
  // History draws first; then the band widens out of it into the future and the
  // median draws through the band.
  const follow = MOTION.draw * MOTION.follow;
  const layout = useChartLayout(CHART.endLabelRoom + CHART.labelGap * 3);
  const historyAt = new Map(history?.years.map((y, i) => [y, i]) ?? []);
  const syntheticAt = new Map(synthetic?.years.map((y, i) => [y, i]) ?? []);
  const data = series.years.map((year, i) => {
    const h = historyAt.get(year);
    const s = syntheticAt.get(year);
    const inScenario = year >= series.from;
    const low = series.p10[i];
    const high = series.p90[i];
    return {
      year,
      history: h != null ? history?.values[h] ?? null : null,
      history__cov: h != null ? history?.coverage?.[h] ?? 1 : 1,
      band: inScenario && low != null && high != null ? [low, high] : null,
      p50: inScenario ? series.p50[i] ?? null : null,
      baseline: baseline && inScenario ? baseline.p50[i] ?? null : null,
      synthetic: s != null && year >= treatmentYear ? synthetic?.values[s] ?? null : null,
    };
  });

  const labels: EndLabelItem[] = [];
  const add = (key: string, label: string, color: string, emphasis = false) => {
    const end = lastPoint(data, key);
    if (end) labels.push({ key, label, x: end[0], y: end[1], color, emphasis });
  };
  add("p50", series.label, theme.text1, true);
  if (baseline) add("baseline", baseline.label, theme.muted);
  if (synthetic) add("synthetic", t("charts.synthetic"), theme.neutral);

  return (
    <ResponsiveContainer width="100%" height={layout.height + CHART.labelGap * 3}>
      <ComposedChart data={data} margin={layout.margin}>
        {grid(theme)}
        {covidBands(theme, layout, covidYears, t)}
        {yearAxis(theme, layout, data)}
        {valueAxis(theme, layout, format)}
        {treatmentLine(theme, layout, treatmentYear, t)}
        {projectionLine(theme, layout, projectionStart, t)}
        {tooltip(theme, { format, keepOrder: true })}
        <Area
          dataKey="band"
          name={t("charts.band", { label: series.label })}
          stroke="none"
          fill={theme.text1}
          fillOpacity={theme.bandOpacity}
          {...drawProps(motion, { begin: MOTION.draw * 0.3, duration: MOTION.band })}
          activeDot={false}
        />
        {baseline ? (
          <Line
            dataKey="baseline"
            name={t("charts.median", { label: baseline.label })}
            stroke={theme.muted}
            strokeWidth={CHART.stroke.comparison}
            strokeDasharray={CHART.dash.baseline}
            dot={false}
            activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
            {...drawProps(motion, { begin: follow })}
          />
        ) : null}
        {synthetic ? (
          <Line
            dataKey="synthetic"
            name={t("charts.syntheticPhase3")}
            stroke={theme.neutral}
            strokeWidth={CHART.stroke.comparison}
            strokeDasharray={CHART.dash.comparison}
            dot={false}
            activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
            {...drawProps(motion, { begin: follow })}
          />
        ) : null}
        <Line
          dataKey="p50"
          name={t("charts.median", { label: series.label })}
          stroke={theme.text1}
          strokeWidth={CHART.stroke.comparison}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...drawProps(motion, { begin: follow })}
        />
        {history ? (
          <Line
            dataKey="history"
            name={t("charts.history")}
            stroke={theme.hero}
            strokeWidth={CHART.stroke.hero}
            dot={false}
            activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
            {...drawProps(motion)}
          />
        ) : null}
        {/* Coverage rings on a static layer, so the caveat never waits for the draw. */}
        {history ? (
          <Line
            dataKey="history"
            stroke="none"
            dot={hollowWhenPartial(theme, theme.hero, "history__cov")}
            activeDot={false}
            isAnimationActive={false}
            legendType="none"
            tooltipType="none"
          />
        ) : null}
        {cursorYear != null ? (
          <ReferenceLine x={cursorYear} stroke={theme.text2} strokeWidth={CHART.stroke.reference} ifOverflow="hidden" />
        ) : null}
        {layout.endLabels ? <EndLabels items={labels} textColor={theme.text2} emphasisColor={theme.text1} /> : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

import { Area, ComposedChart, Line, ResponsiveContainer } from "recharts";

import type { OutcomeResult } from "../api/types";
import { useT } from "../i18n/context";
import { CHART } from "../lib/chartTokens";
import { valueFormatter } from "../lib/format";
import { drawProps, MOTION, useMotion } from "../lib/motion";
import { lastPoint } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { covidBands, grid, tooltip, treatmentLine, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";

/**
 * Real Myanmar (the hero) against synthetic Myanmar (neutral, dashed), with the
 * leave-one-out refits as a soft band. A non-credible synthetic is drawn fainter.
 *
 * On first view it reveals in order: real Myanmar draws, then the synthetic draws
 * in beside it, then the band - and, for a credible outcome only, the post-
 * treatment gap fills. A non-credible gap is never filled: that would dramatize a
 * gap the API says is not an effect.
 */
export function CounterfactualChart({
  outcome,
  country,
  treatmentYear,
  covidYears,
}: {
  outcome: OutcomeResult;
  /** The treated country's name, in the UI language. */
  country: string;
  treatmentYear: number;
  covidYears: number[];
}) {
  const theme = useChartTheme();
  const t = useT();
  const motion = useMotion();
  const layout = useChartLayout();
  const format = valueFormatter(outcome.is_currency);
  const follow = MOTION.draw * MOTION.follow;
  const band = new Map(outcome.leave_one_out_band.map((b) => [b.year, [b.low, b.high] as const]));
  const data = outcome.series.map((p) => ({
    year: p.year,
    actual: p.actual,
    synthetic: p.synthetic,
    loo: band.get(p.year) ?? null,
    gap:
      outcome.credibility.credible && p.year >= treatmentYear && p.actual != null && p.synthetic != null
        ? ([Math.min(p.actual, p.synthetic), Math.max(p.actual, p.synthetic)] as [number, number])
        : null,
  }));
  const credible = outcome.credibility.credible;
  const synthColor = credible ? theme.neutral : theme.muted;
  const labels: EndLabelItem[] = [];
  const actualEnd = lastPoint(data, "actual");
  const syntheticEnd = lastPoint(data, "synthetic");
  if (actualEnd) {
    labels.push({ key: "actual", label: country, x: actualEnd[0], y: actualEnd[1], color: theme.hero, emphasis: true });
  }
  if (syntheticEnd) {
    labels.push({ key: "synthetic", label: t("charts.synthetic"), x: syntheticEnd[0], y: syntheticEnd[1], color: synthColor });
  }

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <ComposedChart data={data} margin={layout.margin}>
        {grid(theme)}
        {covidBands(theme, layout, covidYears, t)}
        {yearAxis(theme, layout, data)}
        {valueAxis(theme, layout, (v) => format(v))}
        {treatmentLine(theme, layout, treatmentYear, t)}
        {tooltip(theme, { format: (v) => format(v), keepOrder: true })}
        <Area
          dataKey="loo"
          name={t("charts.looRange")}
          stroke="none"
          fill={synthColor}
          fillOpacity={theme.bandOpacity}
          {...drawProps(motion, { begin: follow + MOTION.draw * 0.5 })}
          activeDot={false}
        />
        {credible ? (
          <Area
            dataKey="gap"
            name={t("charts.gapAfterCoup")}
            stroke="none"
            fill={theme.hero}
            fillOpacity={theme.bandOpacity}
            {...drawProps(motion, { begin: follow + MOTION.draw * 0.7 })}
            activeDot={false}
            legendType="none"
            tooltipType="none"
          />
        ) : null}
        <Line
          dataKey="synthetic"
          name={credible ? t("charts.syntheticCountry", { country }) : t("charts.syntheticIllustrative", { country })}
          stroke={synthColor}
          strokeWidth={CHART.stroke.comparison}
          strokeDasharray={CHART.dash.comparison}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...drawProps(motion, { begin: follow })}
        />
        <Line
          dataKey="actual"
          name={country}
          stroke={theme.hero}
          strokeWidth={CHART.stroke.hero}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...drawProps(motion)}
        />
        {layout.endLabels ? <EndLabels items={labels} textColor={theme.text2} emphasisColor={theme.text1} /> : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

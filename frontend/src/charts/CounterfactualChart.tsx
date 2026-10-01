import { Area, ComposedChart, Line, ResponsiveContainer } from "recharts";

import type { OutcomeResult } from "../api/types";
import { CHART } from "../lib/chartTokens";
import { valueFormatter } from "../lib/format";
import { lastPoint } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { covidBands, grid, tooltip, treatmentLine, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";

/**
 * Real Myanmar (the hero) against synthetic Myanmar (neutral, dashed), with the
 * leave-one-out refits as a soft band. A non-credible synthetic is drawn fainter.
 */
export function CounterfactualChart({
  outcome,
  treatmentYear,
  covidYears,
}: {
  outcome: OutcomeResult;
  treatmentYear: number;
  covidYears: number[];
}) {
  const theme = useChartTheme();
  const layout = useChartLayout();
  const format = valueFormatter(outcome.is_currency);
  const band = new Map(outcome.leave_one_out_band.map((b) => [b.year, [b.low, b.high] as const]));
  const data = outcome.series.map((p) => ({
    year: p.year,
    actual: p.actual,
    synthetic: p.synthetic,
    loo: band.get(p.year) ?? null,
  }));
  const credible = outcome.credibility.credible;
  const synthColor = credible ? theme.neutral : theme.muted;
  const labels: EndLabelItem[] = [];
  const actualEnd = lastPoint(data, "actual");
  const syntheticEnd = lastPoint(data, "synthetic");
  if (actualEnd) {
    labels.push({ key: "actual", label: "Myanmar", x: actualEnd[0], y: actualEnd[1], color: theme.hero, emphasis: true });
  }
  if (syntheticEnd) {
    labels.push({ key: "synthetic", label: "Synthetic", x: syntheticEnd[0], y: syntheticEnd[1], color: synthColor });
  }

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <ComposedChart data={data} margin={layout.margin}>
        {grid(theme)}
        {covidBands(theme, layout, covidYears)}
        {yearAxis(theme, layout, data)}
        {valueAxis(theme, layout, (v) => format(v))}
        {treatmentLine(theme, layout, treatmentYear)}
        {tooltip(theme, { format: (v) => format(v), keepOrder: true })}
        <Area
          dataKey="loo"
          name="Leave-one-out range"
          stroke="none"
          fill={synthColor}
          fillOpacity={theme.bandOpacity}
          isAnimationActive={false}
          activeDot={false}
        />
        <Line
          dataKey="synthetic"
          name={credible ? "Synthetic Myanmar" : "Synthetic Myanmar (illustrative)"}
          stroke={synthColor}
          strokeWidth={CHART.stroke.comparison}
          strokeDasharray={CHART.dash.comparison}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          isAnimationActive={false}
        />
        <Line
          dataKey="actual"
          name="Myanmar"
          stroke={theme.hero}
          strokeWidth={CHART.stroke.hero}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          isAnimationActive={false}
        />
        {layout.endLabels ? <EndLabels items={labels} textColor={theme.text2} emphasisColor={theme.text1} /> : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

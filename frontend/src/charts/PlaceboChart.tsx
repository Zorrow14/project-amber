import { Line, LineChart, ReferenceLine, ResponsiveContainer } from "recharts";

import type { OutcomeResult } from "../api/types";
import { CHART } from "../lib/chartTokens";
import { signedFormatter } from "../lib/format";
import { lastPoint, pivot } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { covidBands, grid, tooltip, treatmentLine, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels } from "./EndLabels";

/**
 * Myanmar's gap against every donor's placebo gap. Myanmar is the hero: colored,
 * heavy and labelled; placebos are thin neutral lines, and placebos the donors
 * cannot match (poor pre-fit) are fainter and dashed - counted in the p-value,
 * but their "gaps" are fit failures, not effects. Weight, label and dash carry
 * the distinction, not color alone.
 */
export function PlaceboChart({
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
  const format = signedFormatter(outcome.is_currency);
  const rows = outcome.placebos.flatMap((p) => p.gaps.map((g) => ({ unit: p.unit_iso3, ...g })));
  const data = pivot(
    rows,
    (r) => r.year,
    (r) => r.unit,
    (r) => r.value,
  );
  const ordered = [...outcome.placebos].sort((a, b) => Number(a.treated) - Number(b.treated));
  const treated = outcome.placebos.find((p) => p.treated);
  const end = treated ? lastPoint(data, treated.unit_iso3) : null;

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <LineChart data={data} margin={layout.margin}>
        {grid(theme)}
        {covidBands(theme, layout, covidYears)}
        {yearAxis(theme, layout, data)}
        {valueAxis(theme, layout, (v) => format(v))}
        <ReferenceLine y={0} stroke={theme.axis} strokeWidth={CHART.stroke.reference} />
        {treatmentLine(theme, layout, treatmentYear)}
        {tooltip(theme, { format: (v) => format(v) })}
        {ordered.map((p) => (
          <Line
            key={p.unit_iso3}
            dataKey={p.unit_iso3}
            name={p.treated ? `${p.unit_name} (actual)` : `${p.unit_name} placebo${p.poor_fit ? " (poor fit)" : ""}`}
            stroke={p.treated ? theme.hero : p.poor_fit ? theme.faint : theme.muted}
            strokeWidth={p.treated ? CHART.stroke.hero : CHART.stroke.placebo}
            strokeDasharray={p.poor_fit && !p.treated ? CHART.dash.poorFit : undefined}
            dot={false}
            activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        ))}
        {layout.endLabels && treated && end ? (
          <EndLabels
            items={[
              { key: treated.unit_iso3, label: treated.unit_name, x: end[0], y: end[1], color: theme.hero, emphasis: true },
            ]}
            textColor={theme.text2}
            emphasisColor={theme.text1}
          />
        ) : null}
      </LineChart>
    </ResponsiveContainer>
  );
}

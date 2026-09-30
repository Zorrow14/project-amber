import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { OutcomeResult } from "../api/types";
import { signedFormatter } from "../lib/format";
import { pivot } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { axisProps, yearTicks, CHART_HEIGHT, CHART_MARGIN, covidBands, endLabel, tooltipStyle, treatmentLine } from "./common";

/**
 * Myanmar's gap against every donor's placebo gap. Myanmar bold, placebos gray,
 * and placebos the donors cannot match (poor pre-fit) fainter still - they are
 * counted in the p-value but their "gaps" are fit failures, not effects.
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
  const format = signedFormatter(outcome.is_currency);
  const rows = outcome.placebos.flatMap((p) => p.gaps.map((g) => ({ unit: p.unit_iso3, ...g })));
  const data = pivot(
    rows,
    (r) => r.year,
    (r) => r.unit,
    (r) => r.value,
  );
  const ordered = [...outcome.placebos].sort((a, b) => Number(a.treated) - Number(b.treated));
  const last = data.length - 1;

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        {covidBands(theme, covidYears)}
        <XAxis dataKey="year" type="number" domain={["dataMin", "dataMax"]} ticks={yearTicks(data)} {...axisProps(theme)} />
        <YAxis {...axisProps(theme)} tickFormatter={(v: number) => format(v)} width={64} />
        <ReferenceLine y={0} stroke={theme.axis} />
        {treatmentLine(theme, treatmentYear)}
        <Tooltip {...tooltipStyle(theme)} formatter={(value, name) => [format(Number(value)), name]} />
        {ordered.map((p) => (
          <Line
            key={p.unit_iso3}
            dataKey={p.unit_iso3}
            name={p.treated ? `${p.unit_name} (actual)` : `${p.unit_name} placebo${p.poor_fit ? " (poor fit)" : ""}`}
            stroke={p.treated ? theme.ink : p.poor_fit ? theme.placeboFaint : theme.placebo}
            strokeWidth={p.treated ? 3 : 1.5}
            dot={false}
            isAnimationActive={false}
            label={p.treated ? endLabel(theme.ink, p.unit_name, last, true) : false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { OutcomeResult } from "../api/types";
import { valueFormatter } from "../lib/format";
import { useChartTheme } from "../lib/theme";
import { axisProps, yearTicks, CHART_HEIGHT, CHART_MARGIN, covidBands, endLabel, tooltipStyle, treatmentLine } from "./common";

/** Real vs synthetic Myanmar, with the leave-one-out refits as a shaded band. */
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
  const format = valueFormatter(outcome.is_currency);
  const band = new Map(outcome.leave_one_out_band.map((b) => [b.year, [b.low, b.high] as const]));
  const data = outcome.series.map((p) => ({
    year: p.year,
    actual: p.actual,
    synthetic: p.synthetic,
    loo: band.get(p.year) ?? null,
  }));
  const last = data.length - 1;
  const synthColor = outcome.credibility.credible ? theme.series[1] ?? theme.ink : theme.muted;

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <ComposedChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        {covidBands(theme, covidYears)}
        <XAxis dataKey="year" type="number" domain={["dataMin", "dataMax"]} ticks={yearTicks(data)} {...axisProps(theme)} />
        <YAxis {...axisProps(theme)} domain={["auto", "auto"]} tickFormatter={(v: number) => format(v)} width={64} />
        {treatmentLine(theme, treatmentYear)}
        <Tooltip
          {...tooltipStyle(theme)}
          formatter={(value, name) =>
            Array.isArray(value)
              ? [`${format(Number(value[0]))} – ${format(Number(value[1]))}`, name]
              : [format(Number(value)), name]
          }
        />
        <Area
          dataKey="loo"
          name="Leave-one-out range"
          stroke="none"
          fill={synthColor}
          fillOpacity={0.14}
          isAnimationActive={false}
        />
        <Line
          dataKey="synthetic"
          name={outcome.credibility.credible ? "Synthetic Myanmar" : "Synthetic Myanmar (illustrative)"}
          stroke={synthColor}
          strokeWidth={2}
          strokeDasharray="6 4"
          dot={false}
          isAnimationActive={false}
          label={endLabel(theme.inkSecondary, "Synthetic", last)}
        />
        <Line
          dataKey="actual"
          name="Myanmar"
          stroke={theme.ink}
          strokeWidth={3}
          dot={false}
          isAnimationActive={false}
          label={endLabel(theme.ink, "Myanmar", last, true)}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

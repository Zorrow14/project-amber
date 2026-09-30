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

import type { Nullable } from "../api/types";
import { useChartTheme } from "../lib/theme";
import {
  axisProps,
  yearTicks,
  CHART_HEIGHT,
  CHART_MARGIN,
  covidBands,
  endLabel,
  hollowWhenPartial,
  projectionLine,
  tooltipStyle,
  treatmentLine,
} from "./common";

export interface FanSeries {
  years: number[];
  p10: Nullable<number>[];
  p50: Nullable<number>[];
  p90: Nullable<number>[];
  /** First year drawn: where the scenario leaves history. */
  from: number;
  label: string;
}

/** A scenario's p10–p90 band and median, against history and the phase 3 path. */
export function FanChart({
  series,
  color,
  baseline,
  history,
  synthetic,
  treatmentYear,
  projectionStart,
  covidYears,
  format,
}: {
  series: FanSeries;
  color: string;
  baseline?: { label: string; p50: Nullable<number>[] } | null;
  history?: { values: Nullable<number>[]; coverage?: Nullable<number>[]; years: number[] } | null;
  synthetic?: { years: number[]; values: Nullable<number>[] } | null;
  treatmentYear: number;
  projectionStart: number;
  covidYears: number[];
  format: (value: number) => string;
}) {
  const theme = useChartTheme();
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
  const last = data.length - 1;

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT + 40}>
      <ComposedChart data={data} margin={{ ...CHART_MARGIN, right: 132 }}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        {covidBands(theme, covidYears)}
        <XAxis dataKey="year" type="number" domain={["dataMin", "dataMax"]} ticks={yearTicks(data)} {...axisProps(theme)} />
        <YAxis {...axisProps(theme)} domain={["auto", "auto"]} tickFormatter={(v: number) => format(v)} width={64} />
        {treatmentLine(theme, treatmentYear)}
        {projectionLine(theme, projectionStart)}
        <Tooltip
          {...tooltipStyle(theme)}
          formatter={(value, name) =>
            Array.isArray(value)
              ? [`${format(Number(value[0]))} – ${format(Number(value[1]))}`, name]
              : [format(Number(value)), name]
          }
        />
        <Area
          dataKey="band"
          name={`${series.label}: p10–p90`}
          stroke="none"
          fill={color}
          fillOpacity={0.2}
          isAnimationActive={false}
        />
        {baseline ? (
          <Line
            dataKey="baseline"
            name={`${baseline.label} (median)`}
            stroke={theme.muted}
            strokeWidth={1.5}
            strokeDasharray="2 3"
            dot={false}
            isAnimationActive={false}
            label={endLabel(theme.inkSecondary, baseline.label, last)}
          />
        ) : null}
        {synthetic ? (
          <Line
            dataKey="synthetic"
            name="Synthetic control (phase 3)"
            stroke={theme.inkSecondary}
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            isAnimationActive={false}
          />
        ) : null}
        <Line
          dataKey="p50"
          name={`${series.label} (median)`}
          stroke={color}
          strokeWidth={2.5}
          dot={false}
          isAnimationActive={false}
          label={endLabel(theme.ink, series.label, last, true)}
        />
        {history ? (
          <Line
            dataKey="history"
            name="History"
            stroke={theme.ink}
            strokeWidth={3}
            dot={hollowWhenPartial(theme, theme.ink, "history__cov")}
            isAnimationActive={false}
          />
        ) : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

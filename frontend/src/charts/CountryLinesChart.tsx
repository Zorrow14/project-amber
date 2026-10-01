import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Meta } from "../api/types";
import { lastIndexWith } from "../lib/shape";
import { seriesColor, useChartTheme } from "../lib/theme";
import {
  axisProps,
  yearTicks,
  covidBands,
  endLabel,
  hollowWhenPartial,
  tooltipStyle,
  treatmentLine,
  useChartLayout,
} from "./common";

/**
 * One line per country, Myanmar emphasised, colors fixed by meta order.
 * `data` rows are `{year, <iso3>: value, "<iso3>__cov": coverage}`.
 */
export function CountryLinesChart({
  meta,
  data,
  format,
  logScale = false,
  showCoverage = false,
  yLabel,
}: {
  meta: Meta;
  data: Record<string, number | null>[];
  format: (value: number) => string;
  logScale?: boolean;
  showCoverage?: boolean;
  yLabel: string;
}) {
  const theme = useChartTheme();
  const layout = useChartLayout();
  // Draw donors first so Myanmar sits on top.
  const ordered = [...meta.countries].sort((a, b) => Number(a.treated) - Number(b.treated));

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <LineChart data={data} margin={layout.margin}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        {covidBands(theme, meta.covid_years)}
        <XAxis dataKey="year" type="number" domain={["dataMin", "dataMax"]} ticks={yearTicks(data, layout.tickStep)} {...axisProps(theme, layout.fontSize)} />
        <YAxis
          {...axisProps(theme, layout.fontSize)}
          scale={logScale ? "log" : "auto"}
          domain={logScale ? ["auto", "auto"] : [0, "auto"]}
          tickFormatter={(v: number) => format(v)}
          width={layout.yWidth}
          label={
            layout.endLabels
              ? { value: yLabel, angle: -90, position: "insideLeft", fill: theme.muted, fontSize: 12, dx: -2 }
              : undefined
          }
        />
        {treatmentLine(theme, meta.treatment_year, layout.endLabels ? undefined : "Coup", layout.fontSize)}
        <Tooltip
          {...tooltipStyle(theme)}
          formatter={(value, name, item) => {
            const iso3 = String(item.dataKey);
            const coverage = item.payload?.[`${iso3}__cov`];
            const suffix =
              showCoverage && typeof coverage === "number" && coverage < 1
                ? ` (partial: ${Math.round(coverage * 100)}% of indicators)`
                : "";
            return [`${format(Number(value))}${suffix}`, name];
          }}
          labelFormatter={(year) => String(year)}
        />
        {ordered.map((country) => {
          const color = seriesColor(theme, meta.countries.indexOf(country));
          const last = lastIndexWith(data, country.iso3);
          return (
            <Line
              key={country.iso3}
              dataKey={country.iso3}
              name={country.name}
              stroke={color}
              strokeWidth={country.treated ? 3.5 : 1.75}
              strokeOpacity={country.treated ? 1 : 0.9}
              dot={showCoverage ? hollowWhenPartial(theme, color, `${country.iso3}__cov`) : false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
              connectNulls={false}
              // Only Myanmar is labelled in place: donor ends crowd, so the legend names them.
              label={country.treated && layout.endLabels ? endLabel(theme.ink, country.name, last, true) : false}
            />
          );
        })}
      </LineChart>
    </ResponsiveContainer>
  );
}

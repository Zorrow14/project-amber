import { Line, LineChart, ResponsiveContainer } from "recharts";

import type { Meta } from "../api/types";
import { CHART } from "../lib/chartTokens";
import { formatPercent } from "../lib/format";
import { drawProps, useMotion } from "../lib/motion";
import { lastPoint } from "../lib/shape";
import { countryColors, useChartTheme } from "../lib/theme";
import { covidBands, grid, hollowWhenPartial, tooltip, treatmentLine, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";

/**
 * One line per country: the treated country as the hero, the donors recessive,
 * every line labelled at its right end. `data` rows are
 * `{year, <iso3>: value, "<iso3>__cov": coverage}`.
 */
export function CountryLinesChart({
  meta,
  data,
  format,
  logScale = false,
  showCoverage = false,
}: {
  meta: Meta;
  data: Record<string, number | null>[];
  format: (value: number) => string;
  logScale?: boolean;
  showCoverage?: boolean;
}) {
  const theme = useChartTheme();
  const motion = useMotion();
  const layout = useChartLayout();
  const colors = countryColors(theme, meta.countries);
  // Draw donors first so the hero sits on top.
  const ordered = [...meta.countries].sort((a, b) => Number(a.treated) - Number(b.treated));
  const labels: EndLabelItem[] = meta.countries.flatMap((country) => {
    const end = lastPoint(data, country.iso3);
    return end
      ? [
          {
            key: country.iso3,
            label: country.name,
            x: end[0],
            y: end[1],
            color: colors.get(country.iso3) ?? theme.neutral,
            emphasis: country.treated,
          },
        ]
      : [];
  });

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <LineChart data={data} margin={layout.margin}>
        {grid(theme)}
        {covidBands(theme, layout, meta.covid_years)}
        {yearAxis(theme, layout, data)}
        {valueAxis(theme, layout, format, { log: logScale, zero: !logScale })}
        {treatmentLine(theme, layout, meta.treatment_year)}
        {tooltip(theme, {
          format,
          note: showCoverage
            ? ({ dataKey, payload }) => {
                const coverage = payload[`${dataKey}__cov`];
                return typeof coverage === "number" && coverage < 1
                  ? `partial: ${formatPercent(coverage)} of indicators`
                  : null;
              }
            : undefined,
        })}
        {ordered.map((country) => {
          const color = colors.get(country.iso3) ?? theme.neutral;
          return (
            <Line
              key={country.iso3}
              dataKey={country.iso3}
              name={country.name}
              stroke={color}
              strokeWidth={country.treated ? CHART.stroke.hero : CHART.stroke.series}
              dot={false}
              activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
              {...drawProps(motion)}
              connectNulls={false}
            />
          );
        })}
        {/* Coverage rings on their own static layer: Recharts draws a line's dots only
            once its animation ends, and a caveat must never wait for motion. */}
        {showCoverage
          ? ordered.map((country) => (
              <Line
                key={`${country.iso3}-coverage`}
                dataKey={country.iso3}
                stroke="none"
                dot={hollowWhenPartial(theme, colors.get(country.iso3) ?? theme.neutral, `${country.iso3}__cov`)}
                activeDot={false}
                isAnimationActive={false}
                legendType="none"
                tooltipType="none"
              />
            ))
          : null}
        {layout.endLabels ? <EndLabels items={labels} textColor={theme.text2} emphasisColor={theme.text1} /> : null}
      </LineChart>
    </ResponsiveContainer>
  );
}

import { CartesianGrid, ReferenceArea, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";

import { useNarrow } from "../hooks/useNarrow";
import { CHART } from "../lib/chartTokens";
import type { ChartTheme } from "../lib/theme";
import { ChartTooltip, type TooltipOptions } from "./ChartTooltip";

/**
 * The shared chart grammar: one layout per viewport, one axis style, faint
 * horizontal grid only, one tooltip card, and the same quiet reference marks on
 * every time series. Every chart builds from these so they read as one family.
 */

/** Every `step` years from the first, so ticks are evenly spaced whatever the span. */
export function yearTicks(data: { year?: number | null }[], step: number = CHART.yearStep): number[] {
  const years = data.map((d) => d.year).filter((y): y is number => typeof y === "number");
  if (years.length === 0) return [];
  const first = Math.min(...years);
  const last = Math.max(...years);
  const ticks: number[] = [];
  for (let year = first; year <= last; year += step) ticks.push(year);
  return ticks;
}

export interface ChartLayout {
  margin: { top: number; right: number; bottom: number; left: number };
  height: number;
  yWidth: number;
  tickStep: number;
  fontSize: number;
  /** Whether direct end labels fit. At phone width they would squeeze the plot,
   * so identity falls to the series legend, line patterns and the data table. */
  endLabels: boolean;
}

/** Margins and label density for the viewport; `labelRoom` reserves space for end labels. */
export function useChartLayout(labelRoom: number = CHART.endLabelRoom): ChartLayout {
  const narrow = useNarrow();
  return narrow
    ? {
        margin: CHART.marginNarrow,
        height: CHART.heightNarrow,
        yWidth: CHART.yAxisWidthNarrow,
        tickStep: CHART.yearStepNarrow,
        fontSize: CHART.tickFontNarrow,
        endLabels: false,
      }
    : {
        margin: { ...CHART.margin, right: labelRoom },
        height: CHART.height,
        yWidth: CHART.yAxisWidth,
        tickStep: CHART.yearStep,
        fontSize: CHART.tickFont,
        endLabels: true,
      };
}

/** Faint horizontal rules only - no vertical grid, no plot border, no fill. */
export function grid(theme: ChartTheme) {
  return <CartesianGrid stroke={theme.grid} vertical={false} />;
}

/** The year axis: a hairline baseline, muted tabular ticks, no tick marks. `step` overrides the layout's. */
export function yearAxis(
  theme: ChartTheme,
  layout: ChartLayout,
  data: { year?: number | null }[],
  step: number = layout.tickStep,
) {
  return (
    <XAxis
      dataKey="year"
      type="number"
      domain={["dataMin", "dataMax"]}
      ticks={yearTicks(data, step)}
      stroke={theme.axis}
      tick={{ fill: theme.tick, fontSize: layout.fontSize }}
      tickLine={false}
      tickMargin={CHART.labelOffset}
    />
  );
}

/** The value axis: no line, no tick marks, few formatted ticks. */
export function valueAxis(
  theme: ChartTheme,
  layout: ChartLayout,
  format: (value: number) => string,
  options: { log?: boolean; zero?: boolean; domain?: [number, number] } = {},
) {
  return (
    <YAxis
      scale={options.log ? "log" : "auto"}
      domain={options.domain ?? (options.log ? ["auto", "auto"] : options.zero ? [0, "auto"] : ["auto", "auto"])}
      tickFormatter={(v: number) => format(v)}
      tickCount={CHART.yTickCount}
      width={layout.yWidth}
      axisLine={false}
      tickLine={false}
      tick={{ fill: theme.tick, fontSize: layout.fontSize }}
    />
  );
}

/** The shared tooltip card. */
export function tooltip(theme: ChartTheme, options: TooltipOptions) {
  return (
    <Tooltip
      content={(props) => <ChartTooltip {...props} {...options} />}
      cursor={{ stroke: theme.axis, strokeWidth: CHART.stroke.reference }}
      isAnimationActive={false}
    />
  );
}

/** The treatment year: one thin dashed rule with a small quiet label, on every time series. */
export function treatmentLine(theme: ChartTheme, layout: ChartLayout, year: number) {
  return (
    <ReferenceLine
      x={year}
      stroke={theme.reference}
      strokeDasharray={CHART.dash.treatment}
      strokeWidth={CHART.stroke.reference}
      label={{
        value: layout.endLabels ? "Feb 2021 coup" : "Coup",
        position: "insideTopLeft",
        fill: theme.tick,
        fontSize: layout.fontSize,
      }}
    />
  );
}

/** The COVID year(s), shared with every donor: a faint tint, labelled. */
export function covidBands(theme: ChartTheme, layout: ChartLayout, years: number[]) {
  return years.map((year) => (
    <ReferenceArea
      key={`covid-${year}`}
      x1={year - 0.5}
      x2={year + 0.5}
      fill={theme.context}
      fillOpacity={1}
      stroke="none"
      ifOverflow="extendDomain"
      label={
        layout.endLabels
          ? { value: "COVID", position: "insideBottom", fill: theme.tick, fontSize: layout.fontSize }
          : undefined
      }
    />
  ));
}

/** Where scenarios begin. */
export function projectionLine(theme: ChartTheme, layout: ChartLayout, year: number) {
  return (
    <ReferenceLine
      x={year - 0.5}
      stroke={theme.axis}
      strokeWidth={CHART.stroke.reference}
      label={{
        value: "Scenarios →",
        position: "insideTopLeft",
        dy: CHART.labelGap + CHART.labelOffset,
        fill: theme.tick,
        fontSize: layout.fontSize,
      }}
    />
  );
}

interface DotArgs {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: Record<string, unknown>;
}

/**
 * A dot renderer that rings every point computed from partial indicator
 * coverage - the same hollow-point encoding as the committed charts.
 */
export function hollowWhenPartial(theme: ChartTheme, color: string, coverageKey: string) {
  function Dot(args: unknown) {
    const { cx, cy, index, payload } = args as DotArgs;
    const coverage = payload?.[coverageKey];
    if (cx == null || cy == null || typeof coverage !== "number" || coverage >= 1) {
      return <g key={`d-${coverageKey}-${index}`} />;
    }
    return (
      <circle
        key={`d-${coverageKey}-${index}`}
        cx={cx}
        cy={cy}
        r={CHART.marker.hollow}
        fill={theme.surface}
        stroke={color}
        strokeWidth={CHART.marker.hollowStroke}
      />
    );
  }
  return Dot;
}

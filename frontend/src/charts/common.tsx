import { ReferenceArea, ReferenceLine } from "recharts";

import { useNarrow } from "../hooks/useNarrow";
import type { ChartTheme } from "../lib/theme";

export const CHART_HEIGHT = 340;

/** Every other year from the first, so ticks are evenly spaced whatever the span. */
export function yearTicks(data: { year?: number | null }[], step = 2): number[] {
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
  /** Year-tick spacing. */
  tickStep: number;
  /** Whether to draw direct end labels. At phone width they would squeeze the
   * plot to nothing, so identity falls to the legend, line patterns and the table. */
  endLabels: boolean;
  fontSize: number;
}

/**
 * Margins and label density for the current viewport. `rightLabel` is the room
 * the widest end label needs on a wide screen.
 */
export function useChartLayout(rightLabel = 96): ChartLayout {
  const narrow = useNarrow();
  return narrow
    ? {
        margin: { top: 12, right: 12, bottom: 4, left: 0 },
        height: 280,
        yWidth: 52,
        tickStep: 4,
        endLabels: false,
        fontSize: 11,
      }
    : {
        margin: { top: 12, right: rightLabel, bottom: 4, left: 4 },
        height: CHART_HEIGHT,
        yWidth: 64,
        tickStep: 2,
        endLabels: true,
        fontSize: 12,
      };
}

export function axisProps(theme: ChartTheme, fontSize = 12) {
  return {
    stroke: theme.axis,
    tick: { fill: theme.muted, fontSize },
    tickLine: false,
  } as const;
}

export function tooltipStyle(theme: ChartTheme) {
  return {
    contentStyle: {
      background: theme.surface,
      border: `1px solid ${theme.grid}`,
      borderRadius: 8,
      fontSize: 13,
      color: theme.ink,
    },
    labelStyle: { color: theme.ink, fontWeight: 600 },
    itemStyle: { color: theme.inkSecondary },
  } as const;
}

/** Dashed marker at the treatment year, labelled - the point the estimates turn on. */
export function treatmentLine(theme: ChartTheme, year: number, label = "Feb 2021 coup", fontSize = 12) {
  return (
    <ReferenceLine
      x={year}
      stroke={theme.inkSecondary}
      strokeDasharray="4 4"
      label={{ value: label, position: "insideTopLeft", fill: theme.inkSecondary, fontSize }}
    />
  );
}

/** Shaded COVID year(s), shared with every donor. */
export function covidBands(theme: ChartTheme, years: number[]) {
  return years.map((year) => (
    <ReferenceArea
      key={`covid-${year}`}
      x1={year - 0.5}
      x2={year + 0.5}
      fill={theme.context}
      fillOpacity={1}
      stroke="none"
      ifOverflow="extendDomain"
    />
  ));
}

export function projectionLine(theme: ChartTheme, year: number, fontSize = 12) {
  return (
    <ReferenceLine
      x={year - 0.5}
      stroke={theme.axis}
      label={{ value: "Scenarios →", position: "insideTopLeft", fill: theme.muted, fontSize, dy: 18 }}
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
        r={4}
        fill={theme.surface}
        stroke={color}
        strokeWidth={2}
      />
    );
  }
  return Dot;
}

/** A direct label at the series' last point, so identity never rests on color alone. */
export function endLabel(color: string, text: string, lastIndex: number, bold = false) {
  function Label(args: unknown) {
    const { x, y, index } = args as { x?: number; y?: number; index?: number };
    if (index !== lastIndex || x == null || y == null) return <g />;
    return (
      <text
        x={Number(x) + 8}
        y={Number(y)}
        dy={4}
        fill={color}
        fontSize={12}
        fontWeight={bold ? 700 : 500}
      >
        {text}
      </text>
    );
  }
  return Label;
}

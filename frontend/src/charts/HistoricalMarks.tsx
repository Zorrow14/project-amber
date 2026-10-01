import { useId } from "react";
import { ReferenceArea, ReferenceLine } from "recharts";

import type { HistoricalEvent } from "../api/types";
import { CHART } from "../lib/chartTokens";
import type { ChartTheme } from "../lib/theme";
import type { ChartLayout } from "./common";

/**
 * The historical charts' two honesty cues, kept visibly different because they
 * mark different things:
 *
 * - low reliability (the measurements are suspect): 45-degree hatching behind
 *   those years, and the series drawn dotted at series weight;
 * - the modeling window (where the models are calibrated - a scope choice): a
 *   thin capped bracket along the foot of the plot, labelled.
 *
 * Both are keyed in the legend by name, so neither rests on color.
 */

/** A pattern id unique to one chart instance (useId's characters are not url()-safe). */
export function useHatchId(): string {
  return `hatch-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

/** The hatch pattern, declared inside the chart's SVG. */
export function hatchDefs(id: string, color: string) {
  const size = CHART.hatch.size;
  return (
    <defs key="hatch-defs">
      <pattern id={id} patternUnits="userSpaceOnUse" width={size} height={size} patternTransform="rotate(45)">
        <line x1={0} y1={0} x2={0} y2={size} stroke={color} strokeWidth={CHART.hatch.stroke} />
      </pattern>
    </defs>
  );
}

/** Hatching over the low-reliability years, `from` to `to` (exclusive). */
export function lowReliabilityBand(id: string, from: number, to: number) {
  return (
    <ReferenceArea
      key="low-reliability"
      x1={from}
      x2={to}
      fill={`url(#${id})`}
      fillOpacity={1}
      stroke="none"
      ifOverflow="hidden"
    />
  );
}

/**
 * Dated markers as hairlines. On wide screens each is labelled, alternating
 * between two rows so neighbours (1987, 1988) clear; at phone width the labels
 * drop and the frame's notes list the markers instead.
 */
export function eventLines(theme: ChartTheme, layout: ChartLayout, events: HistoricalEvent[], lastYear: number) {
  const span = events.length > 0 ? lastYear - Math.min(...events.map((e) => e.year)) : 0;
  return events.map((event, i) => {
    const nearEnd = lastYear - event.year < span * 0.12;
    return (
      <ReferenceLine
        key={`event-${event.year}`}
        x={event.year}
        stroke={theme.axis}
        strokeWidth={CHART.stroke.reference}
        ifOverflow="hidden"
        label={
          layout.endLabels
            ? {
                value: event.label,
                position: nearEnd ? "insideTopRight" : "insideTopLeft",
                dy: (i % 2) * CHART.eventRow,
                fill: theme.tick,
                fontSize: layout.fontSize,
              }
            : undefined
        }
      />
    );
  });
}

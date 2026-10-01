import { ComposedChart, Line, ResponsiveContainer } from "recharts";

import type { HistoricalEvent } from "../api/types";
import { CHART } from "../lib/chartTokens";
import { drawProps, segmentDraw, useMotion } from "../lib/motion";
import { lastPoint, logDomain } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { grid, tooltip, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";
import { eventLines, hatchDefs, lowReliabilityBand, useHatchId } from "./HistoricalMarks";
import { WindowBracket } from "./WindowBracket";

export interface HistoricalSeries {
  key: string;
  label: string;
  /** The treated country: the hero color and weight. Others are neutral reference lines. */
  hero: boolean;
}

/**
 * Long-run levels on one ruler, with the two honesty cues: hatching and a
 * dotted segment for low-reliability years, and a capped bracket for the
 * modeling window. `data` rows are `{year, <key>, "<key>__low"}` (see
 * `splitByReliability`).
 */
export function HistoricalChart({
  data,
  series,
  events,
  lowFrom,
  lowUntil,
  windowStart,
  format,
}: {
  data: Record<string, number | null>[];
  series: HistoricalSeries[];
  events: HistoricalEvent[];
  /** First low-reliability year, and the first standard year after it; null when none. */
  lowFrom: number | null;
  lowUntil: number | null;
  windowStart: number;
  format: (value: number) => string;
}) {
  const theme = useChartTheme();
  const motion = useMotion();
  const layout = useChartLayout();
  const hatch = useHatchId();
  const years = data.map((d) => Number(d.year));
  const lastYear = years.length > 0 ? Math.max(...years) : windowStart;
  const segments = segmentDraw(motion, years, lowUntil);
  // Reference lines first, so the hero sits on top.
  const ordered = [...series].sort((a, b) => Number(a.hero) - Number(b.hero));
  const labels: EndLabelItem[] = series.flatMap((s) => {
    const end = lastPoint(data, s.key);
    return end
      ? [{ key: s.key, label: s.label, x: end[0], y: end[1], color: s.hero ? theme.hero : theme.neutral, emphasis: s.hero }]
      : [];
  });

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <ComposedChart data={data} margin={layout.margin}>
        {hatchDefs(hatch, theme.hatch)}
        {grid(theme)}
        {lowFrom != null && lowUntil != null ? lowReliabilityBand(hatch, lowFrom, lowUntil) : null}
        {yearAxis(theme, layout, data, layout.endLabels ? CHART.yearStepLong : CHART.yearStepLongNarrow)}
        {valueAxis(theme, layout, format, {
          log: true,
          domain: logDomain(data, series.flatMap((s) => [s.key, `${s.key}__low`]), CHART.logPad),
        })}
        {eventLines(theme, layout, events, lastYear)}
        {tooltip(theme, {
          format,
          keepOrder: true,
          note: ({ dataKey }) => (String(dataKey).endsWith("__low") ? "low reliability" : null),
        })}
        {ordered.flatMap((s) => {
          const color = s.hero ? theme.hero : theme.neutral;
          return [
            <Line
              key={`${s.key}__low`}
              dataKey={`${s.key}__low`}
              name={`${s.label} (low reliability)`}
              stroke={color}
              strokeWidth={CHART.stroke.series}
              strokeDasharray={CHART.dash.lowReliability}
              strokeLinecap="round"
              dot={false}
              activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
              {...segments.low}
              connectNulls={false}
              legendType="none"
            />,
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.label}
              stroke={color}
              strokeWidth={s.hero ? CHART.stroke.hero : CHART.stroke.comparison}
              dot={false}
              activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
              {...(s.hero ? segments.standard : drawProps(motion))}
              connectNulls={false}
            />,
          ];
        })}
        <WindowBracket
          start={windowStart}
          end={lastYear}
          label={layout.endLabels ? `Modeling window, ${windowStart}–${lastYear}` : `Modeling window ${windowStart}+`}
          color={theme.neutral}
          fontSize={layout.fontSize}
        />
        {layout.endLabels ? <EndLabels items={labels} textColor={theme.text2} emphasisColor={theme.text1} /> : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

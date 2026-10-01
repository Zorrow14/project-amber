import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer } from "recharts";

import { CHART } from "../lib/chartTokens";
import { drawProps, MOTION, segmentDraw, useMotion } from "../lib/motion";
import { lastPoint, logDomain } from "../lib/shape";
import { useChartTheme } from "../lib/theme";
import { grid, tooltip, useChartLayout, valueAxis, yearAxis } from "./common";
import { EndLabels, type EndLabelItem } from "./EndLabels";
import { hatchDefs, lowReliabilityBand, useHatchId } from "./HistoricalMarks";
import { WindowBracket } from "./WindowBracket";

/**
 * Myanmar's actual level (the hero, dotted where low reliability) against the
 * illustrative comparator-tracking path (neutral, dashed - a construct, like
 * synthetic Myanmar), the gap between them shaded. `data` rows are
 * `{year, actual, actual__low, path, gap: [low, high]}`.
 */
export function DivergenceChart({
  data,
  pathLabel,
  lowFrom,
  lowUntil,
  windowStart,
  format,
  animate = true,
  cursorYear = null,
}: {
  data: Record<string, number | null | [number, number]>[];
  pathLabel: string;
  lowFrom: number | null;
  lowUntil: number | null;
  windowStart: number;
  format: (value: number) => string;
  /** False while the scrubber drives the data: each step then shows its state at once. */
  animate?: boolean;
  /** The year the scrubber is on; a thin cursor marks it. */
  cursorYear?: number | null;
}) {
  const theme = useChartTheme();
  const motion = { enabled: useMotion().enabled && animate };
  const layout = useChartLayout(CHART.endLabelRoom + CHART.labelGap * 2);
  const hatch = useHatchId();
  const years = data.map((d) => Number(d.year));
  const lastYear = years.length > 0 ? Math.max(...years) : windowStart;
  // Actual draws first (its low-reliability segment, then the rest); the
  // illustrative path follows, and the gap fills once both are on screen.
  const segments = segmentDraw(motion, years, lowUntil);
  const follow = MOTION.draw * MOTION.follow;
  const labels: EndLabelItem[] = [];
  const actualEnd = lastPoint(data, "actual");
  const pathEnd = lastPoint(data, "path");
  if (actualEnd) {
    labels.push({ key: "actual", label: "Myanmar", x: actualEnd[0], y: actualEnd[1], color: theme.hero, emphasis: true });
  }
  if (pathEnd) {
    labels.push({ key: "path", label: "Illustrative path", x: pathEnd[0], y: pathEnd[1], color: theme.neutral });
  }

  return (
    <ResponsiveContainer width="100%" height={layout.height}>
      <ComposedChart data={data} margin={layout.margin}>
        {hatchDefs(hatch, theme.hatch)}
        {grid(theme)}
        {lowFrom != null && lowUntil != null ? lowReliabilityBand(hatch, lowFrom, lowUntil) : null}
        {yearAxis(theme, layout, data as { year?: number | null }[], layout.endLabels ? CHART.yearStepLong : CHART.yearStepLongNarrow)}
        {valueAxis(theme, layout, format, {
          log: true,
          domain: logDomain(data, ["actual", "actual__low", "path"], { ...CHART.logPad, above: CHART.logPad.below }),
        })}
        {tooltip(theme, {
          format,
          keepOrder: true,
          note: ({ dataKey }) => (String(dataKey).endsWith("__low") ? "low reliability" : null),
        })}
        <Area
          dataKey="gap"
          name="Gap"
          stroke="none"
          fill={theme.hero}
          fillOpacity={theme.bandOpacity}
          {...drawProps(motion, { begin: follow + MOTION.draw * 0.5 })}
          activeDot={false}
          legendType="none"
          tooltipType="none"
        />
        <Line
          dataKey="path"
          name={pathLabel}
          stroke={theme.neutral}
          strokeWidth={CHART.stroke.comparison}
          strokeDasharray={CHART.dash.comparison}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...drawProps(motion, { begin: follow })}
        />
        <Line
          dataKey="actual__low"
          name="Myanmar, actual (low reliability)"
          stroke={theme.hero}
          strokeWidth={CHART.stroke.series}
          strokeDasharray={CHART.dash.lowReliability}
          strokeLinecap="round"
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...segments.low}
          connectNulls={false}
        />
        <Line
          dataKey="actual"
          name="Myanmar, actual"
          stroke={theme.hero}
          strokeWidth={CHART.stroke.hero}
          dot={false}
          activeDot={{ r: CHART.marker.active, strokeWidth: 0 }}
          {...segments.standard}
          connectNulls={false}
        />
        {cursorYear != null ? (
          <ReferenceLine x={cursorYear} stroke={theme.text2} strokeWidth={CHART.stroke.reference} ifOverflow="hidden" />
        ) : null}
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

import { usePlotArea, useXAxisScale, useYAxisScale } from "recharts";

import { CHART } from "../lib/chartTokens";

export interface EndLabelItem {
  key: string;
  label: string;
  /** The series' last point, in data coordinates. */
  x: number;
  y: number;
  /** The series color - carried by a short leader, never by the text. */
  color: string;
  emphasis?: boolean;
}

/**
 * Direct labels at the right end of each line, nudged apart so they never
 * overlap. A short leader in the series color ties a nudged label to its line;
 * the text itself stays in text tones. Rendered inside the chart, where the
 * axis scales are known.
 */
export function EndLabels({ items, textColor, emphasisColor }: { items: EndLabelItem[]; textColor: string; emphasisColor: string }) {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();
  const plot = usePlotArea();
  if (!xScale || !yScale || !plot) return null;

  const placed = items
    .map((item) => {
      const px = xScale(item.x);
      const py = yScale(item.y);
      return px == null || py == null || !Number.isFinite(px) || !Number.isFinite(py)
        ? null
        : { ...item, px, py, ly: py };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
    .sort((a, b) => a.py - b.py);

  // Push labels down until none is closer than the gap, then pull the stack back
  // up if it ran past the bottom of the plot.
  const gap = CHART.labelGap;
  for (let i = 1; i < placed.length; i++) {
    const above = placed[i - 1];
    const current = placed[i];
    if (above && current && current.ly - above.ly < gap) current.ly = above.ly + gap;
  }
  const bottom = plot.y + plot.height;
  const last = placed.at(-1);
  if (last && last.ly > bottom) {
    last.ly = bottom;
    for (let i = placed.length - 2; i >= 0; i--) {
      const below = placed[i + 1];
      const current = placed[i];
      if (below && current && below.ly - current.ly < gap) current.ly = below.ly - gap;
    }
  }

  return (
    <g className="end-labels" aria-hidden="true">
      {placed.map((item) => {
        const x = item.px + CHART.labelOffset;
        return (
          <g key={item.key}>
            <line
              x1={item.px + CHART.marker.hollowStroke}
              y1={item.py}
              x2={x - CHART.marker.hollowStroke}
              y2={item.ly}
              stroke={item.color}
              strokeWidth={CHART.stroke.reference}
            />
            <text
              x={x}
              y={item.ly}
              dy="0.32em"
              fill={item.emphasis ? emphasisColor : textColor}
              fontSize={CHART.labelFont}
              fontWeight={item.emphasis ? CHART.labelWeightEmphasis : CHART.labelWeight}
            >
              {item.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}


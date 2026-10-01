import { usePlotArea, useXAxisScale } from "recharts";

import { CHART } from "../lib/chartTokens";

/**
 * The modeling window as a bracket along the foot of the plot, labelled at its
 * right end. Rendered inside the chart, where the x scale is known.
 */
export function WindowBracket({
  start,
  end,
  label,
  color,
  fontSize,
}: {
  start: number;
  end: number;
  label: string;
  color: string;
  fontSize: number;
}) {
  const xScale = useXAxisScale();
  const plot = usePlotArea();
  if (!xScale || !plot) return null;
  const x1 = xScale(start);
  const x2 = xScale(end);
  if (x1 == null || x2 == null || !Number.isFinite(x1) || !Number.isFinite(x2)) return null;
  const y = plot.y + plot.height - CHART.bracket.inset;
  const cap = CHART.bracket.cap / 2;
  return (
    <g className="window-bracket" aria-hidden="true">
      <line x1={x1} y1={y} x2={x2} y2={y} stroke={color} strokeWidth={CHART.stroke.reference} />
      <line x1={x1} y1={y - cap} x2={x1} y2={y + cap} stroke={color} strokeWidth={CHART.stroke.reference} />
      <line x1={x2} y1={y - cap} x2={x2} y2={y + cap} stroke={color} strokeWidth={CHART.stroke.reference} />
      <text x={x2} y={y - cap - CHART.labelOffset / 2} textAnchor="end" fill={color} fontSize={fontSize}>
        {label}
      </text>
    </g>
  );
}

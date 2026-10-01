/**
 * Chart geometry tokens. Recharts takes margins, stroke widths and font sizes as
 * numbers, so they live here rather than in tokens.css - mirroring its scales
 * (the 4px space scale, the 12/11 px text steps). Colors always come from CSS
 * via lib/theme.ts; nothing here is a color.
 */
export const CHART = {
  height: 320,
  heightNarrow: 260,
  /** Room to the right of the plot for direct end labels, by label length. */
  endLabelRoom: 96,
  margin: { top: 16, right: 16, bottom: 4, left: 0 },
  marginNarrow: { top: 12, right: 8, bottom: 4, left: 0 },
  yAxisWidth: 56,
  yAxisWidthNarrow: 48,
  tickFont: 12,
  tickFontNarrow: 11,
  labelFont: 12,
  labelWeight: 450,
  labelWeightEmphasis: 650,
  /** Minimum vertical gap between stacked end labels. */
  labelGap: 14,
  labelOffset: 8,
  yearStep: 2,
  yearStepNarrow: 4,
  /** Decade ticks for the 1960+ historical charts. */
  yearStepLong: 10,
  yearStepLongNarrow: 20,
  yTickCount: 5,
  stroke: {
    hero: 2.75,
    series: 1.5,
    comparison: 1.75,
    placebo: 1.25,
    reference: 1,
  },
  dash: {
    treatment: "3 4",
    comparison: "6 4",
    baseline: "2 3",
    poorFit: "4 3",
    /** Low-reliability years: a dotted line, with round caps, at series weight. */
    lowReliability: "0.5 4",
  },
  /** The low-reliability hatching: 1-unit lines every `size` units, at 45 degrees. */
  hatch: { size: 6, stroke: 1 },
  /** The modeling-window bracket: end caps of `cap`, `inset` above the x-axis. */
  bracket: { cap: 8, inset: 14 },
  /** Event markers: label rows alternate this far apart so neighbours clear. */
  eventRow: 15,
  /** Log-axis headroom: the domain spans min / below to max x above, so lines clear the
   * event labels at the top and the window bracket at the foot. */
  logPad: { below: 1.6, above: 3 },
  marker: { hollow: 4, hollowStroke: 2, active: 4 },
  bar: { size: 14, radius: 3, rowHeight: 32 },
} as const;

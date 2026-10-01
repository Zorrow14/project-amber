import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

import type { OutcomeResult } from "../api/types";
import { CHART } from "../lib/chartTokens";
import { formatPercent } from "../lib/format";
import { useChartTheme } from "../lib/theme";

/**
 * Who synthetic Myanmar is made of: horizontal bars, sorted, labelled with
 * tabular percentages. Recessive by design - zero-weight donors are listed so
 * the whole pool is visible.
 */
export function DonorWeightsChart({
  outcome,
  donors,
}: {
  outcome: OutcomeResult;
  donors: { iso3: string; name: string }[];
}) {
  const theme = useChartTheme();
  const weight = new Map(outcome.weights.map((w) => [w.donor_iso3, w.weight]));
  const data = donors
    .map((d) => ({ name: d.name, weight: weight.get(d.iso3) ?? 0 }))
    .sort((a, b) => b.weight - a.weight);
  const color = outcome.credibility.credible ? theme.neutral : theme.muted;

  return (
    <ResponsiveContainer width="100%" height={CHART.bar.rowHeight * data.length + CHART.margin.top}>
      <BarChart data={data} layout="vertical" margin={{ ...CHART.margin, right: CHART.endLabelRoom / 2 }}>
        <XAxis type="number" domain={[0, 1]} hide />
        <YAxis
          type="category"
          dataKey="name"
          width={CHART.endLabelRoom}
          axisLine={false}
          tickLine={false}
          tick={{ fill: theme.text2, fontSize: CHART.tickFont }}
        />
        <Bar
          dataKey="weight"
          fill={color}
          radius={[0, CHART.bar.radius, CHART.bar.radius, 0]}
          barSize={CHART.bar.size}
          minPointSize={CHART.stroke.series}
          isAnimationActive={false}
        >
          <LabelList
            dataKey="weight"
            position="right"
            formatter={(v: unknown) => formatPercent(Number(v))}
            fill={theme.text2}
            fontSize={CHART.tickFont}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

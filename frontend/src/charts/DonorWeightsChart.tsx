import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

import type { OutcomeResult } from "../api/types";
import { formatPercent } from "../lib/format";
import { useChartTheme } from "../lib/theme";
import { axisProps } from "./common";

/** Who synthetic Myanmar is made of. Zero-weight donors are listed so the pool is visible. */
export function DonorWeightsChart({ outcome, donors }: { outcome: OutcomeResult; donors: { iso3: string; name: string }[] }) {
  const theme = useChartTheme();
  const weight = new Map(outcome.weights.map((w) => [w.donor_iso3, w.weight]));
  const data = donors
    .map((d) => ({ name: d.name, weight: weight.get(d.iso3) ?? 0 }))
    .sort((a, b) => b.weight - a.weight);
  const color = outcome.credibility.credible ? theme.series[1] ?? theme.ink : theme.muted;

  return (
    <ResponsiveContainer width="100%" height={36 * data.length + 16}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 8 }}>
        <XAxis type="number" domain={[0, 1]} hide />
        <YAxis type="category" dataKey="name" width={96} {...axisProps(theme)} axisLine={false} />
        <Bar dataKey="weight" fill={color} radius={[0, 4, 4, 0]} barSize={16} minPointSize={2} isAnimationActive={false}>
          <LabelList
            dataKey="weight"
            position="right"
            formatter={(v: unknown) => formatPercent(Number(v))}
            fill={theme.inkSecondary}
            fontSize={12}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

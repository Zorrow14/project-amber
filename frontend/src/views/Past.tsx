import { useState } from "react";

import { api } from "../api/client";
import { ChartCard, LegendItem } from "../components/ChartCard";
import { Notice } from "../components/Notice";
import { Slider } from "../components/Slider";
import { CountryLinesChart } from "../charts/CountryLinesChart";
import { useMeta } from "../context/metaContext";
import { useApi, useDebounced } from "../hooks/useApi";
import { formatIndex, formatPercent } from "../lib/format";
import { pivot } from "../lib/shape";
import { seriesColor, useChartTheme } from "../lib/theme";
import { GdpDivergence } from "./GdpDivergence";

export function Past() {
  const meta = useMeta();
  const theme = useChartTheme();
  const defaults = Object.fromEntries(meta.pillars.map((p) => [p.id, p.default_weight]));
  const [weights, setWeights] = useState<Record<string, number>>(defaults);
  const settled = useDebounced(weights);
  const index = useApi((signal) => api.index(settled, signal), `index:${JSON.stringify(settled)}`);

  const combined = index.data?.rows.filter((r) => r.series === "combined") ?? [];
  const data = pivot(
    combined,
    (r) => r.year,
    (r) => r.country_iso3,
    (r) => r.value,
    (r) => ({ [`${r.country_iso3}__cov`]: r.coverage }),
  );
  const treated = meta.countries.find((c) => c.treated);
  const partial = combined.filter((r) => r.country_iso3 === treated?.iso3 && r.coverage < 1);
  const inIndex = meta.indicators.filter((i) => i.in_index);
  const excluded = meta.indicators.filter((i) => !i.in_index);
  const total = Object.values(weights).reduce((sum, w) => sum + w, 0);
  const isDefault =meta.pillars.every((p) => weights[p.id] === p.default_weight);

  return (
    <div className="stack">
      <header className="view-head">
        <h2>Past</h2>
        <p className="lede">
          What happened since {meta.modeling_window.start}. Pre-{meta.modeling_window.start} military-era
          statistics are left out: they are not reliable enough to build on.
        </p>
      </header>

      <GdpDivergence meta={meta} />

      <section className="card controls" aria-label="Pillar weights">
        <div className="controls__head">
          <h3>How do you define development?</h3>
          <button className="button button--ghost" onClick={() => setWeights(defaults)} disabled={isDefault}>
            Reset to equal
          </button>
        </div>
        <p className="muted">
          The index is a weighted geometric mean of three pillars, so a strong pillar cannot mask a weak
          one. Weights are relative: only their ratios matter. Each change is recomputed live by the API.
        </p>
        <div className="controls__grid">
          {meta.pillars.map((pillar) => (
            <Slider
              key={pillar.id}
              label={pillar.label}
              value={weights[pillar.id] ?? 0}
              min={0}
              max={1}
              step={0.01}
              onChange={(value) => setWeights((w) => ({ ...w, [pillar.id]: value }))}
              display={(value) => (total > 0 ? formatPercent(value / total) : "–")}
            />
          ))}
        </div>
      </section>

      {index.error ? (
        <Notice tone="warning" title="These weights cannot produce an index">
          <p>{index.error.message}</p>
        </Notice>
      ) : null}

      <ChartCard
        title={`Combined development index, ${meta.modeling_window.start}–${meta.modeling_window.end}`}
        badge={index.loading ? "Updating…" : undefined}
        subtitle={`Scored against fixed goalposts (0.01–1), so every year and country sits on the same ruler. Weights applied: ${meta.pillars
          .map((p) => `${p.label} ${formatPercent(index.data?.weights[p.id] ?? null)}`)
          .join(" · ")}.`}
        legend={[
          ...meta.countries.map((c, i) => (
            <LegendItem key={c.iso3} color={seriesColor(theme, i)} label={c.name} variant={c.treated ? "bold" : "line"} />
          )),
          <LegendItem key="partial" color={theme.inkSecondary} label="Partial indicator coverage" variant="hollow" />,
        ]}
        notes={[
          meta.framing.coverage,
          partial.length > 0
            ? `${treated?.name}'s score is partial from ${Math.min(...partial.map((r) => r.year))}: by ${Math.max(
                ...partial.map((r) => r.year),
              )} it rests on ${formatPercent(partial.at(-1)?.coverage ?? null)} of its indicators.`
            : null,
          `Built from ${inIndex.length} of the panel's ${meta.indicators.length} indicators. ${excluded
            .map((i) => i.name)
            .join(" and ")} stay as history only: no counterfactual or projection can produce them.`,
        ].filter((n): n is string => Boolean(n))}
      >
        <CountryLinesChart
          meta={meta}
          data={data}
          format={(v) => formatIndex(v, 2)}
          showCoverage
          yLabel="Index (0.01–1)"
        />
      </ChartCard>
    </div>
  );
}

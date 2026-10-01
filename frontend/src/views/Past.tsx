import { useState } from "react";

import { api } from "../api/client";
import { Pill } from "../components/Banner";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { ControlPanel } from "../components/ControlPanel";
import { Async } from "../components/LoadState";
import { SectionHeader } from "../components/SectionHeader";
import { Slider } from "../components/Slider";
import { CountryLinesChart } from "../charts/CountryLinesChart";
import { useMeta } from "../context/metaContext";
import { useApi, useDebounced } from "../hooks/useApi";
import { CHART } from "../lib/chartTokens";
import { describeCountryLines, seriesTable } from "../lib/describe";
import { formatIndex, formatPercent } from "../lib/format";
import { pivot } from "../lib/shape";
import { countryColors, useChartTheme } from "../lib/theme";
import { GdpDivergence } from "./GdpDivergence";

export function Past() {
  const meta = useMeta();
  const theme = useChartTheme();
  const colors = countryColors(theme, meta.countries);
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
  const isDefault = meta.pillars.every((p) => weights[p.id] === p.default_weight);
  const format = (v: number) => formatIndex(v, 2);
  const applied = meta.pillars
    .map((p) => `${p.label} ${formatPercent(index.data?.weights[p.id] ?? null)}`)
    .join(" · ");
  const partialFrom = partial.length > 0 ? Math.min(...partial.map((r) => r.year)) : null;
  const partialNote =
    partial.length > 0
      ? `${treated?.name}'s score is partial from ${partialFrom}: by ${Math.max(
          ...partial.map((r) => r.year),
        )} it rests on ${formatPercent(partial.at(-1)?.coverage ?? null)} of its indicators.`
      : null;

  return (
    <div className="view">
      <SectionHeader
        eyebrow="Past"
        title={`What happened since ${meta.modeling_window.start}`}
        description={`Real indicator series for ${treated?.name ?? "Myanmar"} and its peers. Pre-${meta.modeling_window.start} military-era statistics are left out: they are not reliable enough to build on.`}
      />

      <GdpDivergence meta={meta} />

      <section className="section" aria-labelledby="index-title">
        <SectionHeader
          level={2}
          id="index-title"
          title="How do you define development?"
          description="The combined index is a weighted geometric mean of three pillars, so a strong pillar cannot mask a weak one. Set the weights; the API recomputes the index live."
        />

        <ControlPanel
          label="Pillar weights"
          title="Pillar weights"
          description="Relative: only their ratios matter."
          layout="grid"
          action={
            <button className="button button--ghost" onClick={() => setWeights(defaults)} disabled={isDefault}>
              Reset to equal
            </button>
          }
        >
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
        </ControlPanel>

        <ChartFrame
          title={`Combined development index, ${meta.modeling_window.start}–${meta.modeling_window.end}`}
          status={index.loading && index.data ? "Updating…" : undefined}
          subtitle={`Scored against fixed goalposts (0.01–1), so every year and country sits on the same ruler. Weights applied: ${applied}.`}
          callout={
            partialFrom != null ? (
              <Pill tone="caution">
                {treated?.name} partial from {partialFrom}
              </Pill>
            ) : null
          }
          seriesLegend={meta.countries.map((c) => (
            <LegendItem
              key={c.iso3}
              color={colors.get(c.iso3) ?? theme.neutral}
              label={c.name}
              variant={c.treated ? "bold" : "line"}
            />
          ))}
          legend={<LegendItem color={theme.text2} label="Partial indicator coverage" variant="hollow" />}
          notes={[
            meta.framing.coverage,
            partialNote,
            `Built from ${inIndex.length} of the panel's ${meta.indicators.length} indicators. ${excluded
              .map((i) => i.name)
              .join(" and ")} stay as history only: no counterfactual or projection can produce them.`,
          ].filter((n): n is string => Boolean(n))}
          source="Source: World Bank, World Development Indicators; Amber's index."
          summary={[
            describeCountryLines(`the combined development index (0.01–1), weights ${applied}`, data, meta.countries, format),
            "Hollow points mark scores computed from partial indicator coverage.",
            partialNote,
          ]
            .filter(Boolean)
            .join(" ")}
          table={
            data.length > 0
              ? seriesTable(
                  `Combined development index by year and country, weights ${applied}`,
                  data,
                  meta.countries.map((c) => ({ key: c.iso3, label: c.name })),
                  format,
                  (key) => `${key}__cov`,
                )
              : null
          }
        >
          <Async
            state={index}
            what="the index"
            height={CHART.heightNarrow}
            isEmpty={(d) => d.rows.length === 0}
            inputTitle="These weights cannot produce an index"
          >
            {() => <CountryLinesChart meta={meta} data={data} format={format} showCoverage />}
          </Async>
        </ChartFrame>
      </section>
    </div>
  );
}

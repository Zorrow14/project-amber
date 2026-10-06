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
import { useRoute, useUrlState } from "../context/routeContext";
import { useApi, useDebounced } from "../hooks/useApi";
import { useI18n } from "../i18n/context";
import { listAnd } from "../i18n/words";
import { CHART } from "../lib/chartTokens";
import { describeCountryLines, seriesTable } from "../lib/describe";
import { formatIndex, formatPercent } from "../lib/format";
import { pivot } from "../lib/shape";
import { countryColors, useChartTheme } from "../lib/theme";
import { formatNumbers, parseNumbers, snap } from "../lib/url";
import { GdpDivergence } from "./GdpDivergence";

const WEIGHT_STEP = 0.01;

export function Past() {
  const meta = useMeta();
  const theme = useChartTheme();
  const i18n = useI18n();
  const { t } = i18n;
  const colors = countryColors(theme, meta.countries);
  const defaults = Object.fromEntries(meta.pillars.map((p) => [p.id, p.default_weight]));
  const route = useRoute();
  // A shared link names only the weights it changed; the rest keep their defaults exactly.
  const [weights, setWeights] = useState<Record<string, number>>(() => {
    const linked = parseNumbers(route.params.weights);
    return Object.fromEntries(
      meta.pillars.map((p) => {
        const value = linked[p.id];
        return [p.id, value == null ? p.default_weight : snap(value, 0, 1, WEIGHT_STEP)];
      }),
    );
  });
  const changed = Object.fromEntries(meta.pillars.filter((p) => weights[p.id] !== p.default_weight).map((p) => [p.id, weights[p.id] ?? 0]));
  useUrlState({ weights: Object.keys(changed).length > 0 ? formatNumbers(changed) : undefined });
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
  const treatedName = treated?.name ?? meta.treated_country;
  const partial = combined.filter((r) => r.country_iso3 === treated?.iso3 && r.coverage < 1);
  const inIndex = meta.indicators.filter((i) => i.in_index);
  const excluded = meta.indicators.filter((i) => !i.in_index);
  const total = Object.values(weights).reduce((sum, w) => sum + w, 0);
  const isDefault = meta.pillars.every((p) => weights[p.id] === p.default_weight);
  const format = (v: number) => formatIndex(v, 2);
  const applied = meta.pillars
    .map((p) => t("views.past.weight", { pillar: p.label, share: formatPercent(index.data?.weights[p.id] ?? null) }))
    .join(t("meta.middot"));
  const partialFrom = partial.length > 0 ? Math.min(...partial.map((r) => r.year)) : null;
  const partialNote =
    partial.length > 0
      ? t("views.past.partialNote", {
          country: treatedName,
          from: partialFrom ?? "",
          to: Math.max(...partial.map((r) => r.year)),
          share: formatPercent(partial.at(-1)?.coverage ?? null),
        })
      : null;

  return (
    <div className="view">
      <SectionHeader
        eyebrow={t("nav.past")}
        title={t("views.past.title", { year: meta.modeling_window.start })}
        description={t("views.past.description", { country: treatedName, year: meta.modeling_window.start })}
      />

      <GdpDivergence meta={meta} />

      <section className="section" aria-labelledby="index-title">
        <SectionHeader
          level={2}
          id="index-title"
          title={t("views.past.indexTitle")}
          description={t("views.past.indexDescription")}
        />

        <ControlPanel
          label={t("controls.pillarWeights")}
          title={t("controls.pillarWeights")}
          description={t("controls.pillarWeightsHint")}
          layout="grid"
          action={
            <button className="button button--ghost" onClick={() => setWeights(defaults)} disabled={isDefault}>
              {t("controls.resetEqual")}
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
              step={WEIGHT_STEP}
              onChange={(value) => setWeights((w) => ({ ...w, [pillar.id]: value }))}
              display={(value) => (total > 0 ? formatPercent(value / total) : "–")}
            />
          ))}
        </ControlPanel>

        <ChartFrame
          exportName="development-index"
          title={t("views.past.chartTitle", { start: meta.modeling_window.start, end: meta.modeling_window.end })}
          status={index.loading && index.data ? t("banners.updating") : undefined}
          subtitle={t("views.past.chartSubtitle", { weights: applied })}
          callout={
            partialFrom != null ? (
              <Pill tone="caution">{t("honesty.partialFrom", { country: treatedName, year: partialFrom })}</Pill>
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
          legend={<LegendItem color={theme.text2} label={t("honesty.partialCoverage")} variant="hollow" />}
          notes={[
            meta.framing.coverage,
            partialNote,
            t("views.past.builtFrom", {
              n: inIndex.length,
              total: meta.indicators.length,
              excluded: listAnd(
                i18n,
                excluded.map((i) => i.name),
              ),
            }),
          ].filter((n): n is string => Boolean(n))}
          source={t("views.past.source")}
          summary={[
            describeCountryLines(i18n, t("views.past.summaryWhat", { weights: applied }), data, meta.countries, format),
            t("honesty.hollowSummary"),
            partialNote,
          ]
            .filter(Boolean)
            .join(" ")}
          table={
            data.length > 0
              ? seriesTable(
                  i18n,
                  t("views.past.tableCaption", { weights: applied }),
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
            what={t("banners.what.index")}
            height={CHART.heightNarrow}
            isEmpty={(d) => d.rows.length === 0}
            inputTitle={t("views.past.inputTitle")}
          >
            {() => <CountryLinesChart meta={meta} data={data} format={format} showCoverage />}
          </Async>
        </ChartFrame>
      </section>
    </div>
  );
}

import { useState } from "react";

import { api } from "../api/client";
import type { Meta, ScenarioResult, ScenariosResponse, SDCredibility } from "../api/types";
import { Banner } from "../components/Banner";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { ControlGroup } from "../components/ControlPanel";
import { CredibilityBanner } from "../components/CredibilityBanner";
import { Async } from "../components/LoadState";
import { SectionHeader } from "../components/SectionHeader";
import { Slider } from "../components/Slider";
import { FanChart } from "../charts/FanChart";
import { useMeta } from "../context/metaContext";
import { useApi, useDebounced } from "../hooks/useApi";
import { usePlayback } from "../hooks/usePlayback";
import { useI18n, type I18n } from "../i18n/context";
import { listAnd } from "../i18n/words";
import { CHART } from "../lib/chartTokens";
import { seriesTable } from "../lib/describe";
import {
  formatDollars,
  formatIndex,
  formatPercent,
  formatSignedDollars,
  formatSignedIndex,
  withoutLeadingTitle,
} from "../lib/format";
import { useChartTheme } from "../lib/theme";
import { DevelopmentPlayer } from "./DevelopmentPlayer";

const OUTPUT = "Y";

/** Series the fan chart can show: the index, its pillars, and GDP per capita. */
function chartableSeries(meta: Meta) {
  const gdp = meta.sc_outcomes.find((o) => o.is_currency)?.id;
  return meta.sd_series.filter((s) => s.kind === "combined" || s.kind === "pillar" || s.id === gdp);
}

function isCurrencySeries(meta: Meta, id: string): boolean {
  return meta.sc_outcomes.some((o) => o.id === id && o.is_currency) || id === OUTPUT;
}

/** The notes every fan chart carries: consistency, composition, paired gap, ensemble. */
function futureNotes(
  i18n: I18n,
  meta: Meta,
  credibility: SDCredibility,
  result: ScenarioResult,
  seriesId: string,
  years: number[],
): string[] {
  const { t } = i18n;
  const notes: string[] = [];
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;
  const check = result.sc_checks.find((c) => c.outcome === seriesId);
  if (check) {
    if (check.applicable && check.deviation != null) {
      notes.push(
        t(check.consistent ? "views.future.consistent" : "views.future.inconsistent", {
          from: meta.treatment_year,
          to: meta.modeling_window.end,
          deviation: formatPercent(check.deviation),
          tolerance: formatPercent(check.tolerance),
        }),
      );
    } else if (check.reason) {
      notes.push(t("views.future.notCompared", { reason: check.reason }));
    }
  }
  if (seriesId === "combined" && credibility.composition_gap != null) {
    notes.push(
      t("views.future.composition", {
        country: treated,
        year: credibility.last_observed_year,
        gap: formatSignedIndex(credibility.composition_gap),
      }),
    );
  }
  const gap = result.gaps?.[seriesId];
  if (gap) {
    const end = years.length - 1;
    const fmt = isCurrencySeries(meta, seriesId) ? formatSignedDollars : (v: number | null) => formatSignedIndex(v);
    const baseline = meta.scenarios.find((s) => s.name === meta.baseline_scenario)?.label ?? meta.baseline_scenario;
    notes.push(
      t("views.future.paired", {
        p50: fmt(gap.quantiles.p50?.[end] ?? null),
        baseline: baseline.toLowerCase(),
        year: years[end] ?? "",
        p10: fmt(gap.quantiles.p10?.[end] ?? null),
        p90: fmt(gap.quantiles.p90?.[end] ?? null),
        share: formatPercent(gap.share_above[end] ?? null),
      }),
    );
  }
  notes.push(
    t(credibility.profile_flat ? "views.future.ensemble" : "views.future.ensembleSteep", {
      n: meta.ensemble_size,
      count: credibility.unidentified.length,
      labels: listAnd(i18n, credibility.unidentified_labels),
    }),
  );
  return notes;
}

function FutureChart({
  meta,
  scenarios,
  result,
  seriesId,
  loading,
  cursorYear = null,
}: {
  meta: Meta;
  scenarios: ScenariosResponse;
  result: ScenarioResult;
  seriesId: string;
  loading: boolean;
  cursorYear?: number | null;
}) {
  const theme = useChartTheme();
  const i18n = useI18n();
  const { t } = i18n;
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;
  const bands = result.series[seriesId];
  const series = meta.sd_series.find((s) => s.id === seriesId);
  const currency = isCurrencySeries(meta, seriesId);
  const format = currency ? formatDollars : (v: number) => formatIndex(v, 2);
  const years = scenarios.years;
  const from = result.diverges_from ?? scenarios.projection_start;

  const baselineResult = scenarios.scenarios.find((s) => s.name === meta.baseline_scenario);
  const baseline =
    result.name !== meta.baseline_scenario && baselineResult?.series[seriesId]?.p50
      ? { label: baselineResult.label, p50: baselineResult.series[seriesId].p50 ?? [] }
      : null;

  const h = scenarios.history;
  const history =
    seriesId === "combined"
      ? { years: h.years, values: h.combined, coverage: h.combined_coverage }
      : currency
        ? { years: h.years, values: h.gdp_pc }
        : null;
  const overlay = scenarios.sc_overlay.find((o) => o.outcome === seriesId);
  const synthetic = overlay?.credible ? { years: overlay.years, values: overlay.synthetic } : null;

  const notes = futureNotes(i18n, meta, scenarios.credibility, result, seriesId, years);
  const credible = scenarios.credibility.credible;
  const end = years.length - 1;
  const label = series?.label ?? seriesId;
  const lastHistory = history ? history.values.findLastIndex((v) => v != null) : -1;
  const summary = [
    t("views.future.summaryFan", {
      label,
      scenario: result.label,
      from,
      to: years[end] ?? "",
      n: meta.ensemble_size,
    }),
    bands
      ? t("views.future.summaryEnd", {
          year: years[end] ?? "",
          p50: format(Number(bands.p50?.[end])),
          p10: format(Number(bands.p10?.[end])),
          p90: format(Number(bands.p90?.[end])),
        })
      : "",
    history && lastHistory >= 0
      ? t("views.future.summaryHistory", {
          year: history.years[lastHistory] ?? "",
          value: format(Number(history.values[lastHistory])),
        })
      : "",
    seriesId === "combined" ? t("honesty.hollowHistorySummary") : "",
    credible ? t("honesty.scenarioSentence") : t("honesty.backtestFailed"),
  ]
    .filter(Boolean)
    .join(" ");
  const historyAt = new Map(history?.years.map((y, i) => [y, i]) ?? []);
  const table = bands
    ? seriesTable(
        i18n,
        t("views.future.tableCaption", {
          label,
          scenario: result.label,
          suffix: credible ? "" : t("honesty.illustrativeShortSuffix"),
        }),
        years.map((year, i) => {
          const h = historyAt.get(year);
          const inScenario = year >= from;
          return {
            year,
            history: h != null ? history?.values[h] ?? null : null,
            history__cov: h != null ? history?.coverage?.[h] ?? 1 : 1,
            p10: inScenario ? bands.p10?.[i] ?? null : null,
            p50: inScenario ? bands.p50?.[i] ?? null : null,
            p90: inScenario ? bands.p90?.[i] ?? null : null,
            ...(baseline ? { baseline: inScenario ? baseline.p50[i] ?? null : null } : {}),
          };
        }),
        [
          ...(history ? [{ key: "history", label: t("charts.history") }] : []),
          { key: "p10", label: t("charts.p10") },
          { key: "p50", label: t("charts.medianColumn") },
          { key: "p90", label: t("charts.p90") },
          ...(baseline ? [{ key: "baseline", label: t("charts.median", { label: baseline.label }) }] : []),
        ],
        format,
        (key) => (key === "history" ? "history__cov" : "__none"),
      )
    : null;
  if (overlay && !overlay.credible && !result.sc_checks.some((c) => c.outcome === seriesId)) {
    notes.unshift(t("honesty.notOverlaid"));
  }

  return (
    <ChartFrame
      title={t("views.future.chartTitle", { series: label, scenario: result.label, year: meta.horizon_end })}
      badge={credible ? t("honesty.scenarioBadge") : t("honesty.illustrativeDynamics")}
      badgeTone={credible ? "neutral" : "critical"}
      status={loading ? t("banners.updating") : undefined}
      subtitle={t("views.future.chartSubtitle", { from, start: scenarios.projection_start })}
      legend={[
        history ? (
          <LegendItem key="h" color={theme.hero} label={t("charts.countryHistory", { country: treated })} variant="bold" />
        ) : null,
        <LegendItem key="p" color={theme.text1} label={t("charts.median", { label: result.label })} />,
        <LegendItem key="b" color={theme.text1} label={t("charts.p10p90")} variant="band" />,
        baseline ? (
          <LegendItem key="base" color={theme.muted} label={t("charts.median", { label: baseline.label })} variant="dotted" />
        ) : null,
        synthetic ? (
          <LegendItem
            key="s"
            color={theme.neutral}
            label={t("charts.syntheticCountryPhase3", { country: treated })}
            variant="dashed"
          />
        ) : null,
        seriesId === "combined" ? (
          <LegendItem key="c" color={theme.hero} label={t("honesty.partialCoverage")} variant="hollow" />
        ) : null,
      ].filter(Boolean)}
      notes={notes}
      summary={summary}
      table={table}
    >
      {bands ? (
        <FanChart
          series={{
            years,
            p10: bands.p10 ?? [],
            p50: bands.p50 ?? [],
            p90: bands.p90 ?? [],
            from,
            label: result.label,
          }}
          baseline={baseline}
          history={history}
          synthetic={synthetic}
          treatmentYear={meta.treatment_year}
          projectionStart={scenarios.projection_start}
          covidYears={meta.covid_years}
          format={format}
          cursorYear={cursorYear}
        />
      ) : (
        <p className="empty">{t("views.future.notInTrajectory")}</p>
      )}
    </ChartFrame>
  );
}

export function Future() {
  const meta = useMeta();
  const { t } = useI18n();
  const scenarios = useApi(api.scenarios, "scenarios");
  const [scenarioName, setScenarioName] = useState(meta.counterfactual_scenario);
  const scenarioMeta = meta.scenarios.find((s) => s.name === scenarioName) ?? meta.scenarios[0];
  const [levers, setLevers] = useState<Record<string, number>>(scenarioMeta?.levers ?? {});
  const options = chartableSeries(meta);
  const [seriesId, setSeriesId] = useState(options.find((s) => s.kind === "combined")?.id ?? options[0]?.id ?? "");

  const settled = useDebounced(levers);
  const simulated = useApi(
    (signal) => api.simulate({ scenario: scenarioName, levers: settled }, signal),
    `simulate:${scenarioName}:${JSON.stringify(settled)}`,
  );

  const choose = (name: string) => {
    setScenarioName(name);
    setLevers(meta.scenarios.find((s) => s.name === name)?.levers ?? {});
  };
  const custom = meta.levers.some((l) => levers[l.name] !== scenarioMeta?.levers[l.name]);
  const years = scenarios.data?.years ?? [];
  const playback = usePlayback(years.length);
  const cursorYear = playback.scrubbed ? years[playback.index] ?? null : null;
  const credibility = simulated.data?.credibility ?? scenarios.data?.credibility;
  const scenarioTitle = t("honesty.scenarioTitle");

  return (
    <div className="view">
      <SectionHeader
        eyebrow={t("nav.future")}
        title={t("views.future.title", { year: meta.horizon_end })}
        description={t("views.future.description")}
      />

      <div className="stack">
        <Banner tone="info" title={scenarioTitle} kind="framing">
          <p>{withoutLeadingTitle(meta.framing.scenario, scenarioTitle)}</p>
        </Banner>
        {credibility ? (
          <CredibilityBanner
            credible={credibility.credible}
            title={t("honesty.sdNotCredibleTitle")}
            message={credibility.message}
          />
        ) : null}
      </div>

      <div className="split">
        <aside className="card control-panel split__aside" aria-label={t("controls.scenarioAndLevers")}>
          <fieldset className="scenario-picker">
            <legend>{t("controls.stabilityPath")}</legend>
            {meta.scenarios.map((s) => (
              <label key={s.name} className={`scenario ${s.name === scenarioName ? "scenario--active" : ""}`}>
                <input
                  type="radio"
                  name="scenario"
                  value={s.name}
                  checked={s.name === scenarioName}
                  onChange={() => choose(s.name)}
                />
                <span>
                  <span className="scenario__label">{s.label}</span>
                  <span className="scenario__description">{s.description}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <hr className="divider" />

          <ControlGroup
            title={t("controls.policyLevers")}
            description={t("controls.leversHint", { year: meta.projection_start })}
            action={
              <button
                className="button button--ghost"
                onClick={() => setLevers(scenarioMeta?.levers ?? {})}
                disabled={!custom}
              >
                {t("controls.reset")}
              </button>
            }
          >
            {meta.levers.map((lever) => (
              <Slider
                key={lever.name}
                label={lever.label}
                value={levers[lever.name] ?? lever.default}
                min={lever.min}
                max={lever.max}
                step={lever.step}
                onChange={(value) => setLevers((l) => ({ ...l, [lever.name]: value }))}
                display={(value) => t("controls.multiplier", { value: value.toFixed(2) })}
                hint={lever.description}
              />
            ))}
          </ControlGroup>

          <hr className="divider" />

          <label className="select">
            <span>{t("controls.series")}</span>
            <select value={seriesId} onChange={(event) => setSeriesId(event.target.value)}>
              {options.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </aside>

        <div className="split__main stack">
          <Async state={scenarios} what={t("banners.what.scenarios")} height={CHART.height}>
            {(precomputed) => (
              <Async
                state={simulated}
                what={t("banners.what.run")}
                height={CHART.height}
                inputTitle={t("views.future.inputTitle")}
              >
                {(run) => {
                  const baseline =
                    run.result.name === meta.baseline_scenario && !run.result.custom
                      ? null
                      : precomputed.scenarios.find((s) => s.name === meta.baseline_scenario) ?? null;
                  return (
                    <>
                      <FutureChart
                        meta={meta}
                        scenarios={precomputed}
                        result={run.result}
                        seriesId={seriesId}
                        loading={simulated.loading}
                        cursorYear={cursorYear}
                      />
                      <DevelopmentPlayer
                        meta={meta}
                        years={precomputed.years}
                        history={precomputed.history}
                        result={run.result}
                        baseline={baseline}
                        credible={run.credibility.credible}
                        playback={playback}
                      />
                    </>
                  );
                }}
              </Async>
            )}
          </Async>
        </div>
      </div>
    </div>
  );
}

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
import { CHART } from "../lib/chartTokens";
import { seriesTable } from "../lib/describe";
import {
  formatDollars,
  formatIndex,
  formatPercent,
  formatSignedDollars,
  formatSignedIndex,
} from "../lib/format";
import { useChartTheme } from "../lib/theme";

const OUTPUT = "Y";
const SCENARIO_TITLE = "Scenarios, not forecasts";

/** "Scenarios, not forecasts: each shows..." under that title reads "Each shows...". */
function withoutLeadingTitle(text: string, title: string): string {
  if (!text.toLowerCase().startsWith(`${title.toLowerCase()}:`)) return text;
  const rest = text.slice(title.length + 1).trim();
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

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
  meta: Meta,
  credibility: SDCredibility,
  result: ScenarioResult,
  seriesId: string,
  years: number[],
): string[] {
  const notes: string[] = [];
  const treated = meta.countries.find((c) => c.treated)?.name ?? "the treated country";
  const check = result.sc_checks.find((c) => c.outcome === seriesId);
  if (check) {
    if (check.applicable && check.deviation != null) {
      const verdict = check.consistent ? "within" : "beyond";
      notes.push(
        `Over ${meta.treatment_year}–${meta.modeling_window.end} this path runs up to ${formatPercent(check.deviation)} from phase 3's synthetic control, ${verdict} the ${formatPercent(check.tolerance)} tolerance${check.consistent ? "." : ": read it as optimistic."}`,
      );
    } else if (check.reason) {
      notes.push(`Phase 3's synthetic control is not overlaid or compared: ${check.reason}`);
    }
  }
  if (seriesId === "combined" && credibility.composition_gap != null) {
    notes.push(
      `History scores only the indicators ${treated} reports (hollow points); scenarios score all of them. In ${credibility.last_observed_year} that alone lifts the modeled index by ${formatSignedIndex(credibility.composition_gap)} - a composition step, not a scenario effect.`,
    );
  }
  const gap = result.gaps?.[seriesId];
  if (gap) {
    const end = years.length - 1;
    const fmt = isCurrencySeries(meta, seriesId) ? formatSignedDollars : (v: number | null) => formatSignedIndex(v);
    const baseline = meta.scenarios.find((s) => s.name === meta.baseline_scenario)?.label ?? "the baseline";
    notes.push(
      `Paired member by member, this scenario ends ${fmt(gap.quantiles.p50?.[end] ?? null)} against ${baseline.toLowerCase()} in ${years[end]} (p10–p90 ${fmt(gap.quantiles.p10?.[end] ?? null)} to ${fmt(gap.quantiles.p90?.[end] ?? null)}), above it in ${formatPercent(gap.share_above[end] ?? null)} of members.`,
    );
  }
  notes.push(
    `Bands span p10–p90 of a ${meta.ensemble_size}-member ensemble. ${credibility.unidentified.length} parameters the data cannot pin down (${credibility.unidentified_labels.join(" and ")}) are spread over their plausible ranges, with history refitted at each${credibility.profile_flat ? "" : " - and at least one profile node fits worse than tolerance"}.`,
  );
  return notes;
}

function FutureChart({
  meta,
  scenarios,
  result,
  seriesId,
  loading,
}: {
  meta: Meta;
  scenarios: ScenariosResponse;
  result: ScenarioResult;
  seriesId: string;
  loading: boolean;
}) {
  const theme = useChartTheme();
  const treated = meta.countries.find((c) => c.treated)?.name ?? "the treated country";
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

  const notes = futureNotes(meta, scenarios.credibility, result, seriesId, years);
  const credible = scenarios.credibility.credible;
  const end = years.length - 1;
  const label = series?.label ?? seriesId;
  const lastHistory = history ? history.values.findLastIndex((v) => v != null) : -1;
  const summary = [
    `Fan chart of ${label} under the ${result.label} scenario, ${from}–${years[end]}: the median and the p10–p90 range of a ${meta.ensemble_size}-member ensemble.`,
    bands
      ? `In ${years[end]} the median is ${format(Number(bands.p50?.[end]))}, with p10 ${format(Number(bands.p10?.[end]))} and p90 ${format(Number(bands.p90?.[end]))}.`
      : "",
    history && lastHistory >= 0
      ? `History runs to ${history.years[lastHistory]}, ending at ${format(Number(history.values[lastHistory]))}.`
      : "",
    seriesId === "combined" ? "Hollow history points are scored from partial indicator coverage." : "",
    credible ? "A scenario, not a forecast." : "Illustrative dynamics only: the model failed its backtest gate.",
  ]
    .filter(Boolean)
    .join(" ");
  const historyAt = new Map(history?.years.map((y, i) => [y, i]) ?? []);
  const table = bands
    ? seriesTable(
        `${label}, ${result.label}: history and the ensemble's p10, median and p90 by year${credible ? "" : " (illustrative)"}`,
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
          ...(history ? [{ key: "history", label: "History" }] : []),
          { key: "p10", label: "p10" },
          { key: "p50", label: "Median" },
          { key: "p90", label: "p90" },
          ...(baseline ? [{ key: "baseline", label: `${baseline.label} (median)` }] : []),
        ],
        format,
        (key) => (key === "history" ? "history__cov" : "__none"),
      )
    : null;
  if (overlay && !overlay.credible && !result.sc_checks.some((c) => c.outcome === seriesId)) {
    notes.unshift("Phase 3's counterfactual for this series is not credible, so it is not overlaid.");
  }

  return (
    <ChartFrame
      title={`${series?.label ?? seriesId}: ${result.label}, to ${meta.horizon_end}`}
      badge={credible ? "Scenario, not a forecast" : "Illustrative dynamics"}
      badgeTone={credible ? "neutral" : "critical"}
      status={loading ? "Updating…" : undefined}
      subtitle={`The band starts in ${from}, where this scenario leaves history; levers act from ${scenarios.projection_start}.`}
      legend={[
        history ? <LegendItem key="h" color={theme.hero} label={`${treated}, history`} variant="bold" /> : null,
        <LegendItem key="p" color={theme.text1} label={`${result.label} (median)`} />,
        <LegendItem key="b" color={theme.text1} label="p10–p90" variant="band" />,
        baseline ? <LegendItem key="base" color={theme.muted} label={`${baseline.label} (median)`} variant="dotted" /> : null,
        synthetic ? <LegendItem key="s" color={theme.neutral} label={`Synthetic ${treated} (phase 3)`} variant="dashed" /> : null,
        seriesId === "combined" ? (
          <LegendItem key="c" color={theme.hero} label="Partial indicator coverage" variant="hollow" />
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
        />
      ) : (
        <p className="empty">This series is not in the trajectory.</p>
      )}
    </ChartFrame>
  );
}

export function Future() {
  const meta = useMeta();
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
  const credibility = simulated.data?.credibility ?? scenarios.data?.credibility;

  return (
    <div className="view">
      <SectionHeader
        eyebrow="Future"
        title={`What could still happen, to ${meta.horizon_end}`}
        description="Pick a path for stability, then move the policy levers: each change re-runs the calibrated model live. It is never refitted."
      />

      <div className="stack">
        <Banner tone="info" title={SCENARIO_TITLE}>
          <p>{withoutLeadingTitle(meta.framing.scenario, SCENARIO_TITLE)}</p>
        </Banner>
        {credibility ? (
        <CredibilityBanner
          credible={credibility.credible}
          title="Illustrative dynamics, not a calibrated projection"
          message={credibility.message}
        />
        ) : null}
      </div>

      <div className="split">
        <aside className="card control-panel split__aside" aria-label="Scenario and levers">
          <fieldset className="scenario-picker">
            <legend>Stability path</legend>
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
            title="Policy levers"
            description={`Multipliers on reform-era behaviour: 1.0 = as calibrated. They act from ${meta.projection_start}.`}
            action={
              <button
                className="button button--ghost"
                onClick={() => setLevers(scenarioMeta?.levers ?? {})}
                disabled={!custom}
              >
                Reset
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
              display={(value) => `×${value.toFixed(2)}`}
              hint={lever.description}
            />
          ))}
          </ControlGroup>

          <hr className="divider" />

          <label className="select">
            <span>Series</span>
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
          <Async state={scenarios} what="the precomputed scenarios" height={CHART.height}>
            {(precomputed) => (
              <Async
                state={simulated}
                what="the scenario run"
                height={CHART.height}
                inputTitle="These levers cannot be simulated"
              >
                {(run) => (
                  <FutureChart
                    meta={meta}
                    scenarios={precomputed}
                    result={run.result}
                    seriesId={seriesId}
                    loading={simulated.loading}
                  />
                )}
              </Async>
            )}
          </Async>
        </div>
      </div>
    </div>
  );
}

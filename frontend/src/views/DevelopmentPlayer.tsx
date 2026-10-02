import type { History, Meta, Nullable, ScenarioResult } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { Pill } from "../components/Banner";
import { StatCallout, StatRow } from "../components/StatCallout";
import { TimeScrubber } from "../components/TimeScrubber";
import type { Playback } from "../hooks/usePlayback";
import { useI18n } from "../i18n/context";
import { list } from "../i18n/words";
import { formatDollars, formatIndex, formatPercent } from "../lib/format";
import { MOTION } from "../lib/motion";

const index2 = (v: number | null) => formatIndex(v, 2);

/** A value at year `i`, its p10-p90 range, and whether it is history or the scenario. */
function at(
  i: number,
  year: number,
  history: { years: number[]; values: Nullable<number>[]; coverage?: Nullable<number>[] },
  bands: Record<string, Nullable<number>[]> | undefined,
) {
  const h = history.years.indexOf(year);
  const actual = h >= 0 ? history.values[h] ?? null : null;
  if (actual != null) {
    return { value: actual, actual: true, coverage: h >= 0 ? history.coverage?.[h] ?? 1 : 1, low: null, high: null };
  }
  return {
    value: bands?.p50?.[i] ?? null,
    actual: false,
    coverage: 1,
    low: bands?.p10?.[i] ?? null,
    high: bands?.p90?.[i] ?? null,
  };
}

/**
 * Play a scenario year by year: the combined index, GDP per capita and the
 * three pillars move to each year's value - real World Bank history while it
 * exists, then the scenario's ensemble median, with its p10-p90 range. Every
 * value is a real model output; the caveats (scenario badge, source pill,
 * partial coverage) change with the year, never after it.
 */
export function DevelopmentPlayer({
  meta,
  years,
  history,
  result,
  baseline,
  credible,
  playback,
}: {
  meta: Meta;
  years: number[];
  history: History;
  result: ScenarioResult;
  baseline: ScenarioResult | null;
  credible: boolean;
  playback: Playback;
}) {
  const i18n = useI18n();
  const { t } = i18n;
  const i = playback.index;
  const year = years[i] ?? meta.horizon_end;
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;
  const gdpId = meta.sc_outcomes.find((o) => o.is_currency)?.id ?? "";
  const combined = at(
    i,
    year,
    { years: history.years, values: history.combined, coverage: history.combined_coverage },
    result.series.combined,
  );
  const gdp = at(i, year, { years: history.years, values: history.gdp_pc }, result.series[gdpId]);
  const lastHistory = Math.max(
    ...history.years.filter((_, k) => history.combined[k] != null || history.gdp_pc[k] != null),
  );
  const partial = combined.actual && combined.coverage != null && combined.coverage < 1;
  const range = (v: { low: number | null; high: number | null }, f: (n: number | null) => string) =>
    v.low != null && v.high != null ? t("views.future.range", { low: f(v.low), high: f(v.high) }) : "";

  return (
    <section className="card player" aria-labelledby="player-title">
      <div className="player__head">
        <div>
          <h3 className="control-panel__title" id="player-title">
            {t("views.future.playerTitle", { scenario: result.label.toLowerCase() })}
          </h3>
          <p className="control-panel__description">
            {baseline
              ? t("views.future.playerDescriptionTick", {
                  country: treated,
                  year: lastHistory,
                  baseline: baseline.label.toLowerCase(),
                })
              : t("views.future.playerDescription", { country: treated, year: lastHistory })}
          </p>
        </div>
        <div className="player__pills">
          <Pill tone={credible ? "neutral" : "critical"} data-caveat>
            {credible ? t("honesty.scenarioBadge") : t("honesty.illustrativeDynamics")}
          </Pill>
          <Pill tone="status">
            {combined.actual ? t("views.future.yearActual", { year }) : t("views.future.yearScenario", { year })}
          </Pill>
          {partial ? (
            <Pill tone="caution">{t("honesty.partialCoveragePill", { share: formatPercent(combined.coverage) })}</Pill>
          ) : null}
        </div>
      </div>

      <TimeScrubber
        years={years}
        playback={playback}
        label={t("views.future.scrubLabel", { from: years[0] ?? "", to: years.at(-1) ?? "" })}
      />

      <StatRow>
        <StatCallout
          label={t("views.future.combinedIndex", { year })}
          value={index2(combined.value)}
          count={{ value: combined.value, format: index2, duration: MOTION.stepTween }}
          detail={
            combined.actual
              ? partial
                ? t("honesty.partialActual")
                : t("views.future.actual")
              : range(combined, index2)
          }
        />
        <StatCallout
          label={t("views.future.gdpPc", { year })}
          value={formatDollars(gdp.value)}
          count={{ value: gdp.value, format: formatDollars, duration: MOTION.stepTween }}
          detail={gdp.actual ? t("views.future.actualConstant") : range(gdp, formatDollars)}
        />
      </StatRow>

      <ul className="pillars" aria-label={t("views.future.pillarsLabel", { year })}>
        {meta.pillars.map((pillar) => {
          const value = result.series[pillar.id]?.p50?.[i] ?? null;
          const tick = baseline?.series[pillar.id]?.p50?.[i] ?? null;
          return (
            <li key={pillar.id} className="pillar">
              <span className="pillar__label">{pillar.label}</span>
              <span className="pillar-bar" aria-hidden="true">
                <span className="pillar-bar__fill" style={{ transform: `scaleX(${value ?? 0})` }} />
                {tick != null ? <span className="pillar-bar__tick" style={{ left: `${tick * 100}%` }} /> : null}
              </span>
              <span className="pillar__value">
                <AnimatedNumber value={value} format={index2} duration={MOTION.stepTween} />
              </span>
            </li>
          );
        })}
      </ul>
      <p className="player__readout">
        {baseline
          ? t("views.future.readoutBaseline", {
              year,
              baseline: baseline.label.toLowerCase(),
              scores: list(
                i18n,
                meta.pillars.map((p) =>
                  t("views.future.readoutScore", {
                    pillar: p.label.toLowerCase(),
                    value: index2(baseline.series[p.id]?.p50?.[i] ?? null),
                  }),
                ),
              ),
            })
          : t("views.future.isBaseline")}{" "}
        {t("honesty.modelOutputs")}
      </p>
    </section>
  );
}

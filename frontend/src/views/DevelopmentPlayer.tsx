import type { History, Meta, Nullable, ScenarioResult } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { Pill } from "../components/Banner";
import { StatCallout, StatRow } from "../components/StatCallout";
import { TimeScrubber } from "../components/TimeScrubber";
import type { Playback } from "../hooks/usePlayback";
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
  const i = playback.index;
  const year = years[i] ?? meta.horizon_end;
  const treated = meta.countries.find((c) => c.treated)?.name ?? "Myanmar";
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
    v.low != null && v.high != null ? `p10–p90 ${f(v.low)} to ${f(v.high)}` : "";

  return (
    <section className="card player" aria-labelledby="player-title">
      <div className="player__head">
        <div>
          <h3 className="control-panel__title" id="player-title">
            Play {result.label.toLowerCase()} year by year
          </h3>
          <p className="control-panel__description">
            {`${treated}'s World Bank history to ${lastHistory}, then this scenario's ensemble median. The bars are the model's pillar scores on the goalpost scale${baseline ? `; the tick marks ${baseline.label.toLowerCase()}` : ""}.`}
          </p>
        </div>
        <div className="player__pills">
          <Pill tone={credible ? "neutral" : "critical"} data-caveat>
            {credible ? "Scenario, not a forecast" : "Illustrative dynamics"}
          </Pill>
          <Pill tone="status">{combined.actual ? `${year}: actual, World Bank` : `${year}: scenario median`}</Pill>
          {partial ? (
            <Pill tone="caution">{`Partial coverage: ${formatPercent(combined.coverage)} of indicators`}</Pill>
          ) : null}
        </div>
      </div>

      <TimeScrubber years={years} playback={playback} label={`Year, ${years[0]} to ${years.at(-1)}`} />

      <StatRow>
        <StatCallout
          label={`Combined index, ${year}`}
          value={index2(combined.value)}
          count={{ value: combined.value, format: index2, duration: MOTION.stepTween }}
          detail={combined.actual ? (partial ? "Actual, from partial indicator coverage" : "Actual") : range(combined, index2)}
        />
        <StatCallout
          label={`GDP per capita, ${year}`}
          value={formatDollars(gdp.value)}
          count={{ value: gdp.value, format: formatDollars, duration: MOTION.stepTween }}
          detail={gdp.actual ? "Actual, constant 2015 US$" : range(gdp, formatDollars)}
        />
      </StatRow>

      <ul className="pillars" aria-label={`Pillar scores in ${year}`}>
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
          ? `In ${year}, ${baseline.label.toLowerCase()} scores ${meta.pillars
              .map((p) => `${p.label.toLowerCase()} ${index2(baseline.series[p.id]?.p50?.[i] ?? null)}`)
              .join(", ")}.`
          : `This is the baseline scenario itself.`}{" "}
        Model outputs under stated assumptions: what they would imply, not what will happen.
      </p>
    </section>
  );
}

import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { SectionHeader } from "../components/SectionHeader";
import { StatCallout, StatRow } from "../components/StatCallout";
import { useMeta } from "../context/metaContext";
import { useApi } from "../hooks/useApi";
import type { View } from "../hooks/useHashRoute";
import { formatDollars, formatSignedDollars, formatSignedPercent, ordinal } from "../lib/format";
import { GdpDivergence } from "./GdpDivergence";

const LAYERS: { view: View; title: string; question: string; method: string }[] = [
  {
    view: "past",
    title: "Past",
    question: "What happened, 2011 to today?",
    method: "Real indicator series and a combined development index whose pillar weights you set.",
  },
  {
    view: "counterfactual",
    title: "Counterfactual",
    question: "What if the February 2021 coup had not happened?",
    method: "A synthetic Myanmar: a weighted blend of regional peers fitted to Myanmar before 2021.",
  },
  {
    view: "future",
    title: "Future",
    question: "What could still happen, to 2035?",
    method: "A calibrated system-dynamics model with stability and policy levers - scenarios, not forecasts.",
  },
];

export function Overview({ onNavigate }: { onNavigate: (view: View) => void }) {
  const meta = useMeta();
  const counterfactual = useApi(api.counterfactual, "counterfactual");
  const gdp = counterfactual.data?.outcomes.find((o) => o.is_currency);
  const treated = meta.countries.find((c) => c.treated)?.name ?? "Myanmar";

  // The headline numbers are stated only if the estimate behind them is credible.
  const credible = gdp?.credibility.credible ? gdp : undefined;
  const headline = credible
    ? `By ${credible.latest.year}, ${treated}'s real GDP per capita was ${formatSignedDollars(credible.latest.gap)} (${formatSignedPercent(credible.latest_gap_share)}) against a synthetic ${treated} built from its peers - an estimate against a constructed comparison, not a forecast.`
    : undefined;

  return (
    <div className="view">
      <section className="hero">
        <SectionHeader
          eyebrow={`${treated}, ${meta.modeling_window.start}–${meta.horizon_end}`}
          title="Two timelines, side by side."
          display
          description={`Amber reconstructs ${treated}'s development since the reform era, estimates what the 2021 coup cost against a synthetic comparison, and lets you explore what could still happen.`}
        />
        <p className="framing">
          <Icon name="scale" />
          <span>{meta.framing.project}</span>
        </p>
      </section>

      {credible ? (
        <StatRow>
          <StatCallout
            label={`GDP per capita gap, ${credible.latest.year}`}
            value={formatSignedPercent(credible.latest_gap_share)}
            detail={`against synthetic ${treated}: an estimate, not a forecast`}
          />
          <StatCallout
            label="In dollars per person"
            value={formatSignedDollars(credible.latest.gap)}
            detail={`${formatDollars(credible.latest.actual)} actual against ${formatDollars(credible.latest.synthetic)} synthetic`}
          />
          <StatCallout
            label="Placebo rank"
            value={`${ordinal(credible.metrics.rank)} of ${credible.metrics.n_units}`}
            detail={
              credible.metrics.pseudo_p_value <= credible.metrics.p_value_floor
                ? `p = ${credible.metrics.pseudo_p_value.toFixed(2)}, the smallest ${credible.metrics.n_units} units allow`
                : `p = ${credible.metrics.pseudo_p_value.toFixed(2)}; the smallest possible is ${credible.metrics.p_value_floor.toFixed(2)}`
            }
          />
        </StatRow>
      ) : null}

      <GdpDivergence meta={meta} subtitle={headline} />

      <section className="section" aria-labelledby="layers-title">
        <SectionHeader
          level={2}
          id="layers-title"
          title="Three layers, one ruler"
          description="Each layer answers one question with its own method; one development index measures all three."
        />
        <div className="layers">
          {LAYERS.map((layer) => (
            <button key={layer.view} className="card card--interactive" onClick={() => onNavigate(layer.view)}>
              <span className="layer__eyebrow">{layer.title}</span>
              <span className="layer__title">{layer.question}</span>
              <span className="layer__method">{layer.method}</span>
              <span className="layer__cta">Open {layer.title.toLowerCase()} →</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

import { api } from "../api/client";
import { useMeta } from "../context/metaContext";
import { useApi } from "../hooks/useApi";
import type { View } from "../hooks/useHashRoute";
import { formatSignedDollars, formatSignedPercent } from "../lib/format";
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

  // The headline number is stated only if the estimate behind it is credible.
  const headline =
    gdp && gdp.credibility.credible
      ? `By ${gdp.latest.year}, Myanmar's real GDP per capita was ${formatSignedDollars(gdp.latest.gap)} (${formatSignedPercent(gdp.latest_gap_share)}) against a synthetic Myanmar built from its peers - an estimate against a constructed comparison, not a forecast.`
      : undefined;

  return (
    <div className="stack">
      <section className="hero">
        <p className="eyebrow">Myanmar, {meta.modeling_window.start}–{meta.horizon_end}</p>
        <h1>Two timelines, side by side.</h1>
        <p className="lede">
          Amber reconstructs Myanmar's development since the reform era, estimates what the 2021 coup
          cost against a synthetic comparison, and lets you explore what could still happen.
        </p>
        <p className="framing">{meta.framing.project}</p>
      </section>

      <GdpDivergence meta={meta} subtitle={headline} />

      <section className="layers" aria-label="The three layers">
        {LAYERS.map((layer) => (
          <button key={layer.view} className="card layer" onClick={() => onNavigate(layer.view)}>
            <span className="layer__title">{layer.title}</span>
            <span className="layer__question">{layer.question}</span>
            <span className="layer__method">{layer.method}</span>
            <span className="layer__cta">Open {layer.title.toLowerCase()} →</span>
          </button>
        ))}
      </section>
    </div>
  );
}

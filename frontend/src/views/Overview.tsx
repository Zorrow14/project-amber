import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { SectionHeader } from "../components/SectionHeader";
import { StatCallout, StatRow } from "../components/StatCallout";
import { useMeta } from "../context/metaContext";
import { useApi } from "../hooks/useApi";
import type { View } from "../hooks/useHashRoute";
import { useI18n } from "../i18n/context";
import { rankOf } from "../i18n/words";
import { formatDollars, formatSignedDollars, formatSignedPercent } from "../lib/format";
import { GdpDivergence } from "./GdpDivergence";

const LAYERS = ["past", "counterfactual", "future"] as const satisfies readonly View[];

export function Overview({ onNavigate }: { onNavigate: (view: View) => void }) {
  const meta = useMeta();
  const i18n = useI18n();
  const { t } = i18n;
  const counterfactual = useApi(api.counterfactual, "counterfactual");
  const gdp = counterfactual.data?.outcomes.find((o) => o.is_currency);
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;

  // The headline numbers are stated only if the estimate behind them is credible.
  const credible = gdp?.credibility.credible ? gdp : undefined;
  const headline = credible
    ? t("honesty.headline", {
        year: credible.latest.year,
        country: treated,
        gap: formatSignedDollars(credible.latest.gap),
        share: formatSignedPercent(credible.latest_gap_share),
      })
    : undefined;
  const layers = {
    past: {
      question: t("views.overview.pastQuestion", { year: meta.modeling_window.start }),
      method: t("views.overview.pastMethod"),
    },
    counterfactual: {
      question: t("views.overview.counterfactualQuestion", { year: meta.treatment_year }),
      method: t("views.overview.counterfactualMethod", { country: treated, year: meta.treatment_year }),
    },
    future: {
      question: t("views.overview.futureQuestion", { year: meta.horizon_end }),
      method: t("views.overview.futureMethod"),
    },
  };

  return (
    <div className="view">
      <section className="hero">
        <SectionHeader
          eyebrow={t("views.overview.eyebrow", { country: treated, start: meta.modeling_window.start, end: meta.horizon_end })}
          title={t("views.overview.title")}
          display
          description={t("views.overview.description", { country: treated, year: meta.treatment_year })}
        />
        <p className="framing">
          <Icon name="scale" />
          <span>{meta.framing.project}</span>
        </p>
      </section>

      {credible ? (
        <StatRow>
          <StatCallout
            label={t("views.overview.gapLabel", { year: credible.latest.year })}
            value={formatSignedPercent(credible.latest_gap_share)}
            count={{ value: credible.latest_gap_share, from: 0, format: formatSignedPercent }}
            detail={t("honesty.estimateNotForecast", { country: treated })}
          />
          <StatCallout
            label={t("views.overview.dollarsLabel")}
            value={formatSignedDollars(credible.latest.gap)}
            count={{ value: credible.latest.gap, from: 0, format: (v) => formatSignedDollars(v == null ? null : Math.round(v)) }}
            detail={t("views.overview.dollarsDetail", {
              actual: formatDollars(credible.latest.actual),
              synthetic: formatDollars(credible.latest.synthetic),
            })}
          />
          <StatCallout
            label={t("views.overview.placeboRank")}
            value={rankOf(i18n, credible.metrics.rank, credible.metrics.n_units)}
            detail={
              credible.metrics.pseudo_p_value <= credible.metrics.p_value_floor
                ? t("views.overview.pAtFloor", {
                    p: credible.metrics.pseudo_p_value.toFixed(2),
                    n: credible.metrics.n_units,
                  })
                : t("views.overview.pAboveFloor", {
                    p: credible.metrics.pseudo_p_value.toFixed(2),
                    floor: credible.metrics.p_value_floor.toFixed(2),
                  })
            }
          />
        </StatRow>
      ) : null}

      <GdpDivergence meta={meta} subtitle={headline} />

      <section className="section" aria-labelledby="layers-title">
        <SectionHeader
          level={2}
          id="layers-title"
          title={t("views.overview.layersTitle")}
          description={t("views.overview.layersDescription")}
        />
        <div className="layers">
          {LAYERS.map((view) => (
            <button key={view} className="card card--interactive" onClick={() => onNavigate(view)}>
              <span className="layer__eyebrow">{t(`nav.${view}`)}</span>
              <span className="layer__title">{layers[view].question}</span>
              <span className="layer__method">{layers[view].method}</span>
              <span className="layer__cta">{t("views.overview.open", { view: t(`nav.${view}`).toLowerCase() })}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

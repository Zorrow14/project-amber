import { api } from "../api/client";
import type { Meta, OutcomeResult } from "../api/types";
import { ChartCard, LegendItem } from "../components/ChartCard";
import { CredibilityBanner } from "../components/CredibilityBanner";
import { CounterfactualChart } from "../charts/CounterfactualChart";
import { DonorWeightsChart } from "../charts/DonorWeightsChart";
import { PlaceboChart } from "../charts/PlaceboChart";
import { useMeta } from "../context/metaContext";
import { useApi } from "../hooks/useApi";
import { formatPercent, formatSignedPercent, ordinal, signedFormatter } from "../lib/format";
import { useChartTheme } from "../lib/theme";

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {detail ? <span className="stat__detail">{detail}</span> : null}
    </div>
  );
}

/**
 * One outcome's counterfactual. A non-credible fit is not a weaker estimate but
 * no estimate: the banner leads, the charts are badged illustrative, and the
 * latest gap is not presented as an effect.
 */
export function OutcomeSection({ outcome, meta }: { outcome: OutcomeResult; meta: Meta }) {
  const theme = useChartTheme();
  const { credible } = outcome.credibility;
  const signed = signedFormatter(outcome.is_currency);
  const m = outcome.metrics;
  const treated = meta.countries.find((c) => c.treated)?.name ?? "Myanmar";
  const donors = meta.countries.filter((c) => c.donor);
  const poorFit = outcome.placebos.filter((p) => p.poor_fit).map((p) => p.unit_name);
  const badge = credible ? undefined : "Illustrative only";

  const gapLine = credible
    ? `${outcome.latest.year} gap: ${signed(outcome.latest.gap)} (${formatSignedPercent(outcome.latest_gap_share)}) against synthetic ${treated}.`
    : `The ${outcome.latest.year} gap is not reported: without a credible pre-${meta.treatment_year} fit it measures the fit's failure, not an effect.`;

  return (
    <section className="stack outcome" aria-labelledby={`outcome-${outcome.outcome}`}>
      <h3 className="outcome__title" id={`outcome-${outcome.outcome}`}>
        {outcome.label}
      </h3>
      <CredibilityBanner
        credible={credible}
        title="Not a credible effect estimate"
        message={outcome.credibility.message}
      />

      <div className="stats">
        <Stat
          label={`Pre-${meta.treatment_year} fit error`}
          value={formatPercent(m.pre_rmse_share, 1)}
          detail={`of ${treated}'s level; credible at ≤ ${formatPercent(outcome.credibility.threshold)}`}
        />
        <Stat
          label="Placebo rank"
          value={`${ordinal(m.rank)} of ${m.n_units}`}
          detail={`p = ${m.pseudo_p_value.toFixed(2)}; the smallest possible with ${m.n_units} units is ${m.p_value_floor.toFixed(2)}`}
        />
        <Stat
          label="Donors weighted"
          value={String(m.n_weighted_donors)}
          detail={`effective ${m.n_effective_donors.toFixed(1)} (1/Σw²)`}
        />
      </div>

      <ChartCard
        title={`${treated} and synthetic ${treated}`}
        badge={badge}
        subtitle={gapLine}
        legend={[
          <LegendItem key="a" color={theme.ink} label={treated} variant="bold" />,
          <LegendItem key="s" color={credible ? theme.series[1] ?? theme.ink : theme.muted} label={`Synthetic ${treated}`} variant="dashed" />,
          <LegendItem key="b" color={credible ? theme.series[1] ?? theme.ink : theme.muted} label="Leave-one-out range" variant="band" />,
        ]}
        notes={[
          `Synthetic ${treated} is a convex blend of donors fitted to ${meta.modeling_window.start}–${meta.treatment_year - 1}; after ${meta.treatment_year} the gap between the lines is the estimate.`,
          meta.framing.fiscal_year,
        ]}
      >
        <CounterfactualChart outcome={outcome} treatmentYear={meta.treatment_year} covidYears={meta.covid_years} />
      </ChartCard>

      <div className="grid-2">
        <ChartCard
          title="Gap against the placebos"
          badge={badge}
          subtitle={`Each donor refitted as if it had been treated in ${meta.treatment_year}. A real effect should stand out from the gray.`}
          legend={[
            <LegendItem key="m" color={theme.ink} label={treated} variant="bold" />,
            <LegendItem key="p" color={theme.placebo} label="Placebo donors" />,
            <LegendItem key="f" color={theme.placeboFaint} label="Poor pre-fit" />,
          ]}
          notes={[
            poorFit.length > 0
              ? `Faint: ${poorFit.join(", ")} - pre-fit error over ${meta.thresholds.sc_placebo_poor_fit_multiple}× ${treated}'s; still counted in the p-value.`
              : null,
          ].filter((n): n is string => Boolean(n))}
        >
          <PlaceboChart outcome={outcome} treatmentYear={meta.treatment_year} covidYears={meta.covid_years} />
        </ChartCard>
        <ChartCard title={`Who synthetic ${treated} is made of`} badge={badge} subtitle="Donor weights; they are non-negative and sum to 100%.">
          <DonorWeightsChart outcome={outcome} donors={donors} />
        </ChartCard>
      </div>
    </section>
  );
}

export function Counterfactual() {
  const meta = useMeta();
  const { data, error } = useApi(api.counterfactual, "counterfactual");

  return (
    <div className="stack">
      <header className="view-head">
        <h2>Counterfactual</h2>
        <p className="lede">
          No country shows what Myanmar would have looked like without the coup, so Amber builds one: a
          weighted blend of peers that did not rupture in {meta.treatment_year}, matched to Myanmar
          before it. These are estimates against a constructed comparison, precomputed and never refitted
          on request.
        </p>
      </header>
      {error ? <p className="error">{error.message}</p> : null}
      {!data && !error ? <p className="muted">Loading the counterfactual…</p> : null}
      {data?.outcomes.map((outcome) => (
        <OutcomeSection key={outcome.outcome} outcome={outcome} meta={meta} />
      ))}
    </div>
  );
}

import { api } from "../api/client";
import type { Meta, OutcomeResult } from "../api/types";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { CredibilityBanner } from "../components/CredibilityBanner";
import { Async } from "../components/LoadState";
import { SectionHeader } from "../components/SectionHeader";
import { StatCallout, StatRow } from "../components/StatCallout";
import { CounterfactualChart } from "../charts/CounterfactualChart";
import { DonorWeightsChart } from "../charts/DonorWeightsChart";
import { PlaceboChart } from "../charts/PlaceboChart";
import { useMeta } from "../context/metaContext";
import { useApi } from "../hooks/useApi";
import { CHART } from "../lib/chartTokens";
import { seriesTable } from "../lib/describe";
import { formatPercent, formatSignedPercent, ordinal, signedFormatter, valueFormatter } from "../lib/format";
import { pivot } from "../lib/shape";
import { useChartTheme } from "../lib/theme";

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
  const value = valueFormatter(outcome.is_currency);
  const fmt = (v: number) => value(v);
  const fmtSigned = (v: number) => signed(v);
  const first = outcome.series[0];
  const caveat = credible ? "" : " Illustrative only: the pre-coup fit is not credible, so the gap is not an effect estimate.";

  const mainSummary = `Line chart of ${outcome.label}, ${first?.year}–${outcome.latest.year}: ${treated} and synthetic ${treated}, a blend of donors fitted before ${meta.treatment_year}. In ${outcome.latest.year}, ${treated} is ${value(outcome.latest.actual)} and synthetic ${treated} ${value(outcome.latest.synthetic)}.${caveat}`;
  const mainTable = seriesTable(
    `${outcome.label}: ${treated}, synthetic ${treated} and the gap, by year${credible ? "" : " (illustrative only)"}`,
    outcome.series.map((p) => ({ year: p.year, actual: p.actual, synthetic: p.synthetic, gap: p.gap })),
    [
      { key: "actual", label: treated },
      { key: "synthetic", label: `Synthetic ${treated}` },
      { key: "gap", label: credible ? "Gap" : "Gap (not an effect)" },
    ],
    fmt,
  );
  const placeboRows = pivot(
    outcome.placebos.flatMap((p) => p.gaps.map((g) => ({ unit: p.unit_iso3, ...g }))),
    (r) => r.year,
    (r) => r.unit,
    (r) => r.value,
  );
  const placeboSummary = `Line chart of the gap between each unit and its synthetic control, ${treated} against ${outcome.placebos.length - 1} placebo donors refitted as if treated in ${meta.treatment_year}. ${treated} ranks ${ordinal(m.rank)} of ${m.n_units} on post/pre fit ratio (p = ${m.pseudo_p_value.toFixed(2)}).${poorFit.length > 0 ? ` Dashed, faint: ${poorFit.join(", ")}, poor pre-fit.` : ""}${caveat}`;
  const placeboTable = seriesTable(
    `Gap from synthetic control by year: ${treated} and each placebo${credible ? "" : " (illustrative only)"}`,
    placeboRows,
    outcome.placebos.map((p) => ({
      key: p.unit_iso3,
      label: p.treated ? treated : `${p.unit_name}${p.poor_fit ? " (poor fit)" : ""}`,
    })),
    fmtSigned,
  );
  const weightOf = new Map(outcome.weights.map((w) => [w.donor_iso3, w.weight]));
  const weightRows = donors
    .map((d) => ({ name: d.name, weight: weightOf.get(d.iso3) ?? 0 }))
    .sort((a, b) => b.weight - a.weight);
  const weightSummary = `Bar chart of donor weights, which are non-negative and sum to 100%: ${weightRows
    .map((w) => `${w.name} ${formatPercent(w.weight)}`)
    .join(", ")}.${caveat}`;

  const gapLine = credible
    ? `${outcome.latest.year} gap: ${signed(outcome.latest.gap)} (${formatSignedPercent(outcome.latest_gap_share)}) against synthetic ${treated}.`
    : `The ${outcome.latest.year} gap is not reported: without a credible pre-${meta.treatment_year} fit it measures the fit's failure, not an effect.`;

  return (
    <section className="section outcome" aria-labelledby={`outcome-${outcome.outcome}`}>
      <SectionHeader level={2} id={`outcome-${outcome.outcome}`} title={outcome.label} />
      <CredibilityBanner
        credible={credible}
        title="Not a credible effect estimate"
        message={outcome.credibility.message}
      />

      <StatRow>
        <StatCallout
          label={`Pre-${meta.treatment_year} fit error`}
          value={formatPercent(m.pre_rmse_share, 1)}
          detail={`of ${treated}'s level; credible at ≤ ${formatPercent(outcome.credibility.threshold)}`}
        />
        <StatCallout
          label="Placebo rank"
          value={`${ordinal(m.rank)} of ${m.n_units}`}
          detail={`p = ${m.pseudo_p_value.toFixed(2)}; the smallest possible with ${m.n_units} units is ${m.p_value_floor.toFixed(2)}`}
        />
        <StatCallout
          label="Donors weighted"
          value={String(m.n_weighted_donors)}
          detail={`effective ${m.n_effective_donors.toFixed(1)} (1/Σw²)`}
        />
      </StatRow>

      <ChartFrame
        title={`${treated} and synthetic ${treated}`}
        badge={badge}
        subtitle={gapLine}
        legend={[
          <LegendItem key="a" color={theme.hero} label={treated} variant="bold" />,
          <LegendItem key="s" color={credible ? theme.neutral : theme.muted} label={`Synthetic ${treated}`} variant="dashed" />,
          <LegendItem key="b" color={credible ? theme.neutral : theme.muted} label="Leave-one-out range" variant="band" />,
        ]}
        notes={[
          `Synthetic ${treated} is a convex blend of donors fitted to ${meta.modeling_window.start}–${meta.treatment_year - 1}; after ${meta.treatment_year} the gap between the lines is the estimate.`,
          meta.framing.fiscal_year,
        ]}
        summary={mainSummary}
        table={mainTable}
      >
        <CounterfactualChart outcome={outcome} treatmentYear={meta.treatment_year} covidYears={meta.covid_years} />
      </ChartFrame>

      <div className="grid-2">
        <ChartFrame
          title="Gap against the placebos"
          badge={badge}
          subtitle={`Each donor refitted as if it had been treated in ${meta.treatment_year}. A real effect should stand out from the gray.`}
          legend={[
            <LegendItem key="m" color={theme.hero} label={treated} variant="bold" />,
            <LegendItem key="p" color={theme.muted} label="Placebo donors" />,
            <LegendItem key="f" color={theme.faint} label="Poor pre-fit" variant="dashed" />,
          ]}
          notes={[
            poorFit.length > 0
              ? `Faint and dashed: ${poorFit.join(", ")} - pre-fit error over ${meta.thresholds.sc_placebo_poor_fit_multiple}× ${treated}'s; still counted in the p-value.`
              : null,
          ].filter((n): n is string => Boolean(n))}
          summary={placeboSummary}
          table={placeboTable}
        >
          <PlaceboChart outcome={outcome} treatmentYear={meta.treatment_year} covidYears={meta.covid_years} />
        </ChartFrame>
        <ChartFrame
          title={`Who synthetic ${treated} is made of`}
          badge={badge}
          subtitle="Donor weights; they are non-negative and sum to 100%."
          summary={weightSummary}
          table={{
            caption: `Donor weights in synthetic ${treated}`,
            columns: ["Donor", "Weight"],
            rows: weightRows.map((w) => [w.name, formatPercent(w.weight, 1)]),
          }}
        >
          <DonorWeightsChart outcome={outcome} donors={donors} />
        </ChartFrame>
      </div>
    </section>
  );
}

export function Counterfactual() {
  const meta = useMeta();
  const counterfactual = useApi(api.counterfactual, "counterfactual");

  return (
    <div className="view">
      <SectionHeader
        eyebrow="Counterfactual"
        title={`What if the ${meta.treatment_year} coup had not happened?`}
        description={`No country shows what Myanmar would have looked like without the coup, so Amber builds one: a weighted blend of peers that did not rupture in ${meta.treatment_year}, matched to Myanmar before it. These are estimates against a constructed comparison, precomputed and never refitted on request.`}
      />
      <Async
        state={counterfactual}
        what="the counterfactual"
        height={CHART.height}
        isEmpty={(d) => d.outcomes.length === 0}
      >
        {(data) =>
          data.outcomes.map((outcome) => <OutcomeSection key={outcome.outcome} outcome={outcome} meta={meta} />)
        }
      </Async>
    </div>
  );
}

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
import { useI18n } from "../i18n/context";
import { list, rankOf } from "../i18n/words";
import { CHART } from "../lib/chartTokens";
import { seriesTable } from "../lib/describe";
import { formatPercent, formatSignedPercent, signedFormatter, valueFormatter } from "../lib/format";
import { pivot } from "../lib/shape";
import { useChartTheme } from "../lib/theme";

/**
 * One outcome's counterfactual. A non-credible fit is not a weaker estimate but
 * no estimate: the banner leads, the charts are badged illustrative, and the
 * latest gap is not presented as an effect.
 */
export function OutcomeSection({ outcome, meta }: { outcome: OutcomeResult; meta: Meta }) {
  const theme = useChartTheme();
  const i18n = useI18n();
  const { t } = i18n;
  const { credible } = outcome.credibility;
  const signed = signedFormatter(outcome.is_currency);
  const m = outcome.metrics;
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;
  const donors = meta.countries.filter((c) => c.donor);
  const poorFit = outcome.placebos.filter((p) => p.poor_fit).map((p) => p.unit_name);
  const badge = credible ? undefined : t("honesty.illustrativeOnly");
  const value = valueFormatter(outcome.is_currency);
  const fmt = (v: number) => value(v);
  const fmtSigned = (v: number) => signed(v);
  const first = outcome.series[0];
  const caveat = credible ? "" : t("honesty.fitNotCredible");
  const suffix = credible ? "" : t("honesty.illustrativeSuffix");
  const rank = rankOf(i18n, m.rank, m.n_units);

  const mainSummary = t("views.counterfactual.mainSummary", {
    outcome: outcome.label,
    from: first?.year ?? "",
    to: outcome.latest.year,
    country: treated,
    treatment: meta.treatment_year,
    actual: value(outcome.latest.actual),
    synthetic: value(outcome.latest.synthetic),
    caveat,
  });
  const mainTable = seriesTable(
    i18n,
    t("views.counterfactual.mainTable", { outcome: outcome.label, country: treated, suffix }),
    outcome.series.map((p) => ({ year: p.year, actual: p.actual, synthetic: p.synthetic, gap: p.gap })),
    [
      { key: "actual", label: treated },
      { key: "synthetic", label: t("charts.syntheticCountry", { country: treated }) },
      { key: "gap", label: credible ? t("charts.gap") : t("honesty.gapNotEffect") },
    ],
    fmt,
  );
  const placeboRows = pivot(
    outcome.placebos.flatMap((p) => p.gaps.map((g) => ({ unit: p.unit_iso3, ...g }))),
    (r) => r.year,
    (r) => r.unit,
    (r) => r.value,
  );
  const placeboSummary = t("views.counterfactual.placeboSummary", {
    country: treated,
    n: outcome.placebos.length - 1,
    treatment: meta.treatment_year,
    rank,
    p: m.pseudo_p_value.toFixed(2),
    poor: poorFit.length > 0 ? t("views.counterfactual.placeboSummaryPoor", { names: list(i18n, poorFit) }) : "",
    caveat,
  });
  const placeboTable = seriesTable(
    i18n,
    t("views.counterfactual.placeboTable", { country: treated, suffix }),
    placeboRows,
    outcome.placebos.map((p) => ({
      key: p.unit_iso3,
      label: p.treated
        ? treated
        : p.poor_fit
          ? t("views.counterfactual.poorFitName", { name: p.unit_name })
          : p.unit_name,
    })),
    fmtSigned,
  );
  const weightOf = new Map(outcome.weights.map((w) => [w.donor_iso3, w.weight]));
  const weightRows = donors
    .map((d) => ({ name: d.name, weight: weightOf.get(d.iso3) ?? 0 }))
    .sort((a, b) => b.weight - a.weight);
  const weightSummary = t("views.counterfactual.weightsSummary", {
    weights: list(
      i18n,
      weightRows.map((w) => t("views.counterfactual.weight", { name: w.name, share: formatPercent(w.weight) })),
    ),
    caveat,
  });

  const gapLine = credible
    ? t("views.counterfactual.gapLine", {
        year: outcome.latest.year,
        gap: signed(outcome.latest.gap),
        share: formatSignedPercent(outcome.latest_gap_share),
        country: treated,
      })
    : t("honesty.gapNotReported", { year: outcome.latest.year, treatment: meta.treatment_year });

  return (
    <section className="section outcome" aria-labelledby={`outcome-${outcome.outcome}`}>
      <SectionHeader level={2} id={`outcome-${outcome.outcome}`} title={outcome.label} />
      <CredibilityBanner
        credible={credible}
        title={t("honesty.scNotCredibleTitle")}
        message={outcome.credibility.message}
      />

      <StatRow>
        <StatCallout
          label={t("views.counterfactual.fitError", { year: meta.treatment_year })}
          value={formatPercent(m.pre_rmse_share, 1)}
          detail={t("views.counterfactual.fitErrorDetail", {
            country: treated,
            threshold: formatPercent(outcome.credibility.threshold),
          })}
        />
        <StatCallout
          label={t("views.overview.placeboRank")}
          value={rank}
          detail={t("views.counterfactual.placeboRankDetail", {
            p: m.pseudo_p_value.toFixed(2),
            n: m.n_units,
            floor: m.p_value_floor.toFixed(2),
          })}
        />
        <StatCallout
          label={t("views.counterfactual.donorsWeighted")}
          value={String(m.n_weighted_donors)}
          detail={t("views.counterfactual.donorsEffective", { n: m.n_effective_donors.toFixed(1) })}
        />
      </StatRow>

      <ChartFrame
        title={t("views.counterfactual.mainTitle", { country: treated })}
        badge={badge}
        subtitle={gapLine}
        legend={[
          <LegendItem key="a" color={theme.hero} label={treated} variant="bold" />,
          <LegendItem
            key="s"
            color={credible ? theme.neutral : theme.muted}
            label={t("charts.syntheticCountry", { country: treated })}
            variant="dashed"
          />,
          <LegendItem key="b" color={credible ? theme.neutral : theme.muted} label={t("charts.looRange")} variant="band" />,
          credible ? (
            <LegendItem key="g" color={theme.hero} label={t("charts.gapAfter", { year: meta.treatment_year })} variant="band" />
          ) : null,
        ].filter(Boolean)}
        notes={[
          t("views.counterfactual.mainNote", {
            country: treated,
            start: meta.modeling_window.start,
            end: meta.treatment_year - 1,
            treatment: meta.treatment_year,
          }),
          meta.framing.fiscal_year,
        ]}
        summary={mainSummary}
        table={mainTable}
      >
        <CounterfactualChart
          outcome={outcome}
          country={treated}
          treatmentYear={meta.treatment_year}
          covidYears={meta.covid_years}
        />
      </ChartFrame>

      <div className="grid-2">
        <ChartFrame
          title={t("views.counterfactual.placeboTitle")}
          badge={badge}
          subtitle={t("views.counterfactual.placeboSubtitle", { year: meta.treatment_year })}
          legend={[
            <LegendItem key="m" color={theme.hero} label={treated} variant="bold" />,
            <LegendItem key="p" color={theme.muted} label={t("views.counterfactual.placeboDonors")} />,
            <LegendItem key="f" color={theme.faint} label={t("views.counterfactual.poorPreFit")} variant="dashed" />,
          ]}
          notes={[
            poorFit.length > 0
              ? t("views.counterfactual.poorFitNote", {
                  names: list(i18n, poorFit),
                  multiple: meta.thresholds.sc_placebo_poor_fit_multiple,
                  country: treated,
                })
              : null,
          ].filter((n): n is string => Boolean(n))}
          summary={placeboSummary}
          table={placeboTable}
        >
          <PlaceboChart outcome={outcome} treatmentYear={meta.treatment_year} covidYears={meta.covid_years} />
        </ChartFrame>
        <ChartFrame
          title={t("views.counterfactual.weightsTitle", { country: treated })}
          badge={badge}
          subtitle={t("views.counterfactual.weightsSubtitle")}
          summary={weightSummary}
          table={{
            caption: t("views.counterfactual.weightsTable", { country: treated }),
            columns: [t("views.counterfactual.donor"), t("views.counterfactual.weightColumn")],
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
  const { t } = useI18n();
  const counterfactual = useApi(api.counterfactual, "counterfactual");
  const treated = meta.countries.find((c) => c.treated)?.name ?? meta.treated_country;

  return (
    <div className="view">
      <SectionHeader
        eyebrow={t("nav.counterfactual")}
        title={t("views.counterfactual.title", { year: meta.treatment_year })}
        description={t("views.counterfactual.description", { country: treated, year: meta.treatment_year })}
      />
      <Async
        state={counterfactual}
        what={t("banners.what.counterfactual")}
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

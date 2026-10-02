"""Turn tables and live results into response models.

Precomputed responses (meta, counterfactual, scenarios) are built once per
store; the live ones reuse the same builders, so a live run and a precomputed
one have exactly the same shape.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from amber import __version__, config, i18n
from amber.config import Normalization, Scenario
from amber.modeling import system_dynamics as sd

from . import schemas as s
from .store import DataStore, bool_or_none, finite_or_none

__all__ = [
    "counterfactual",
    "data_info",
    "divergence",
    "health",
    "historical",
    "historical_meta",
    "index_response",
    "meta",
    "panel",
    "scenario_result",
    "scenarios",
    "sd_credibility",
]

SERIES_LABELS: dict[str, str] = {
    "K": "Physical capital per head (2015 US$)",
    "H": "Human capital (2011 = 1)",
    "I": "Connectivity: internet users (%)",
    "S": "Institutional stability (reform era = 1)",
    "Y": "Output: GDP per capita (2015 US$)",
}
"""Labels for the model's own quantities; indicators and pillars use config names."""

PARAMETER_LABELS: dict[str, str] = {
    "connectivity_tfp": "the connectivity effect on productivity (kappa)",
    "savings_rate": "the savings rate",
}
"""Readable names for the parameters the UI mentions; others fall back to their id."""

PILLAR_LABELS: dict[str, str] = {
    "economy": "Economy",
    "innovation": "Innovation / technology",
    "human_development": "Human development",
    "combined": "Combined index",
}


def _l(english: str) -> s.Localized:
    """``english`` with its Burmese twin from the label map (``amber.i18n``)."""
    return s.Localized(**i18n.text(english))


def _floats(values: Sequence[object]) -> list[float | None]:
    return [finite_or_none(v) for v in values]


def data_info(store: DataStore) -> s.DataInfo:
    """Which snapshot is being served."""
    manifest = store.manifest
    return s.DataInfo(
        source=str(store.source),
        built_at=manifest.built_at if manifest else None,
        commit=manifest.commit if manifest else None,
    )


def health(store: DataStore) -> s.HealthResponse:
    """Liveness and provenance."""
    return s.HealthResponse(
        status="ok", service="amber", version=__version__, data=data_info(store)
    )


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #


def _stability(scenario: Scenario) -> list[s.StabilityPoint]:
    return [s.StabilityPoint(year=int(y), recovery=float(r)) for y, r in scenario.stability]


def _levers(scenario: Scenario) -> dict[str, float]:
    return {name: float(scenario.lever(name)) for name in config.LEVERS}


def meta(store: DataStore) -> s.MetaResponse:
    """Everything the frontend needs, derived from config."""
    labels = (
        [(name, SERIES_LABELS[name], "stock") for name in sd.STOCKS]
        + [(i, config.INDICATORS_BY_ID[i].name, "indicator") for i in config.INDEX_INDICATORS]
        + [(str(p), PILLAR_LABELS[str(p)], "pillar") for p in config.Pillar]
        + [(config.COMBINED_SERIES, PILLAR_LABELS[config.COMBINED_SERIES], "combined")]
    )
    sd_series = [
        s.SeriesMeta(id=id_, label=label, label_i18n=_l(label), kind=kind)
        for id_, label, kind in labels
    ]
    framing = {
        "project": config.PROJECT_FRAMING,
        "scenario": config.SCENARIO_FRAMING,
        "sd_not_credible": config.SD_NOT_CREDIBLE_MESSAGE,
        "sc_not_credible": config.SC_NOT_CREDIBLE_MESSAGE,
        "coverage": config.COVERAGE_MESSAGE,
        "fiscal_year": config.FISCAL_YEAR_MESSAGE,
    }
    return s.MetaResponse(
        locales=list(i18n.LOCALES),
        default_locale=i18n.DEFAULT_LOCALE,
        translation_review_pending=len(i18n.REVIEW),
        framing=s.Framing(**framing),
        framing_i18n=s.FramingI18n(**{key: _l(text) for key, text in framing.items()}),
        treated_country=config.TREATED_COUNTRY,
        countries=[
            s.CountryMeta(
                iso3=iso3,
                name=name,
                name_i18n=_l(name),
                treated=iso3 == config.TREATED_COUNTRY,
                donor=iso3 in config.DONOR_POOL,
            )
            for iso3, name in config.COUNTRIES.items()
        ],
        indicators=[
            s.IndicatorMeta(
                id=ind.id,
                name=ind.name,
                name_i18n=_l(ind.name),
                pillar=str(ind.pillar),
                polarity=str(config.INDICATOR_POLARITY[ind.id]),
                in_index=ind.id in config.INDEX_INDICATORS,
                excluded_reason=config.INDEX_EXCLUDED.get(ind.id),
                excluded_reason_i18n=_l(config.INDEX_EXCLUDED[ind.id])
                if ind.id in config.INDEX_EXCLUDED
                else None,
                goalpost_low=config.GOALPOSTS[ind.id].low,
                goalpost_high=config.GOALPOSTS[ind.id].high,
                log_scale=ind.id in config.LOG_TRANSFORM,
            )
            for ind in config.INDICATORS
        ],
        pillars=[
            s.PillarMeta(
                id=str(p),
                label=PILLAR_LABELS[str(p)],
                label_i18n=_l(PILLAR_LABELS[str(p)]),
                default_weight=w,
            )
            for p, w in config.DEFAULT_PILLAR_WEIGHTS.items()
        ],
        normalizations=[str(n) for n in Normalization],
        default_normalization=str(config.DEFAULT_NORMALIZATION),
        treatment_year=config.TREATMENT_YEAR,
        modeling_window=s.Window(start=config.MODELING_WINDOW_START, end=config.YEAR_END),
        covid_years=list(config.COVID_CONFOUNDED_YEARS),
        projection_start=config.SD_PROJECTION_START,
        horizon_end=config.SD_HORIZON_END,
        levers=[
            s.LeverMeta(
                name=name,
                label=lever.label,
                label_i18n=_l(lever.label),
                description=lever.description,
                description_i18n=_l(lever.description),
                min=lever.low,
                max=lever.high,
                step=lever.step,
                default=lever.default,
            )
            for name, lever in config.LEVERS.items()
        ],
        scenarios=[
            s.ScenarioMeta(
                name=sc.name,
                label=sc.label,
                label_i18n=_l(sc.label),
                description=sc.description,
                description_i18n=_l(sc.description),
                levers=_levers(sc),
                stability=_stability(sc),
                diverges_from=sd.divergence_year(sc),
            )
            for sc in config.SCENARIOS
        ],
        baseline_scenario=config.SD_BASELINE_SCENARIO,
        counterfactual_scenario=config.SD_COUNTERFACTUAL_SCENARIO,
        quantiles=list(config.SD_QUANTILES),
        ensemble_size=config.SD_ENSEMBLE_SIZE,
        sc_outcomes=[
            s.OutcomeMeta(
                id=o.name,
                label=o.label,
                label_i18n=_l(o.label),
                units=o.units,
                units_i18n=_l(o.units),
                is_currency=o.is_currency,
            )
            for o in config.SC_OUTCOMES
        ],
        sd_series=sd_series,
        historical=historical_meta(store),
        thresholds=s.Thresholds(
            sc_credible_pre_rmse_share=config.SC_CREDIBLE_PRE_RMSE_SHARE,
            sc_placebo_poor_fit_multiple=config.SC_PLACEBO_POOR_FIT_MULTIPLE,
            sd_credible_nrmse=config.SD_CREDIBLE_NRMSE,
            sd_sc_tolerance=config.SD_SC_TOLERANCE,
            sd_profile_tolerance=config.SD_PROFILE_TOLERANCE,
        ),
        data=data_info(store),
    )


# --------------------------------------------------------------------------- #
# Panel and index
# --------------------------------------------------------------------------- #


def panel(
    store: DataStore,
    indicators: Sequence[str],
    countries: Sequence[str],
    include_pre_window: bool,
) -> s.PanelResponse:
    """Tidy panel rows for the requested indicators and countries."""
    frame = store.panel
    frame = frame[
        frame[config.COL_INDICATOR_ID].isin(indicators)
        & frame[config.COL_COUNTRY_ISO3].isin(countries)
    ]
    if not include_pre_window:
        frame = frame[~frame[config.COL_PRE_2011].astype(bool)]
    frame = frame.sort_values([config.COL_INDICATOR_ID, config.COL_COUNTRY_ISO3, config.COL_YEAR])
    rows = [
        s.PanelRow(
            country_iso3=r.country_iso3,
            indicator_id=r.indicator_id,
            year=int(r.year),
            value=finite_or_none(r.value),
            imputed=bool(bool_or_none(r.imputed)),
        )
        for r in frame.itertuples(index=False)
    ]
    report = store.table(config.COVERAGE_REPORT_STEM)
    report = report[
        report[config.COL_INDICATOR_ID].isin(indicators)
        & report[config.COL_COUNTRY_ISO3].isin(countries)
    ]
    coverage = [
        s.SeriesCoverage(
            country_iso3=r.country_iso3,
            indicator_id=r.indicator_id,
            last_year_observed=(
                None if pd.isna(r.last_year_observed) else int(r.last_year_observed)
            ),
            is_dark=bool(bool_or_none(r.is_dark)),
        )
        for r in report.itertuples(index=False)
    ]
    return s.PanelResponse(
        indicators=list(indicators), countries=list(countries), rows=rows, coverage=coverage
    )


def index_response(
    weights: dict[str, float], method: Normalization, frame: pd.DataFrame
) -> s.IndexResponse:
    """Index rows, each with its coverage."""
    frame = frame.sort_values([config.COL_COUNTRY_ISO3, config.COL_SERIES, config.COL_YEAR])
    return s.IndexResponse(
        method=str(method),
        weights=weights,
        computed_live=True,
        coverage_note=config.COVERAGE_MESSAGE,
        coverage_note_i18n=_l(config.COVERAGE_MESSAGE),
        rows=[
            s.IndexRow(
                country_iso3=r.country_iso3,
                country_name=r.country_name,
                country_name_i18n=_l(r.country_name),
                year=int(r.year),
                series=r.series,
                value=float(r.value),
                coverage=float(r.coverage),
            )
            for r in frame.itertuples(index=False)
        ],
    )


# --------------------------------------------------------------------------- #
# Counterfactual
# --------------------------------------------------------------------------- #


def _sc_points(frame: pd.DataFrame) -> list[s.SCPoint]:
    wide = frame.pivot_table(
        index=config.COL_YEAR, columns=config.COL_SERIES, values=config.COL_VALUE
    )
    return [
        s.SCPoint(
            year=int(year),
            actual=finite_or_none(row.get("actual")),
            synthetic=finite_or_none(row.get("synthetic")),
            gap=finite_or_none(row.get("gap")),
        )
        for year, row in wide.iterrows()
    ]


def _outcome(store: DataStore, outcome: config.SCOutcome) -> s.OutcomeResult:
    name = outcome.name
    metrics = store.table(config.SC_METRICS_STEM).set_index(config.COL_OUTCOME).loc[name]
    credible = bool(bool_or_none(metrics["credible"]))
    share = float(metrics["pre_rmse_share"])

    paths = store.table(config.SC_STEM)
    series = _sc_points(paths[paths[config.COL_OUTCOME] == name])
    latest = max((p for p in series if p.gap is not None), key=lambda p: p.year)

    weights = store.table(config.SC_WEIGHTS_STEM)
    weights = weights[weights[config.COL_OUTCOME] == name].sort_values("weight", ascending=False)

    placebo = store.table(config.SC_PLACEBO_STEM)
    placebo = placebo[placebo[config.COL_OUTCOME] == name]
    pre = placebo[placebo[config.COL_YEAR] <= config.SC_PRE_PERIOD_END]
    pre_rmse = pre.groupby("unit_iso3")["gap"].apply(lambda g: float(np.sqrt(np.mean(g**2))))
    treated_rmse = float(pre_rmse[config.TREATED_COUNTRY])
    limit = config.SC_PLACEBO_POOR_FIT_MULTIPLE * treated_rmse
    placebos = []
    for unit, rows in placebo.groupby("unit_iso3", sort=False):
        is_treated = unit == config.TREATED_COUNTRY
        placebos.append(
            s.Placebo(
                unit_iso3=str(unit),
                unit_name=config.COUNTRIES[str(unit)],
                unit_name_i18n=_l(config.COUNTRIES[str(unit)]),
                treated=is_treated,
                pre_rmse=float(pre_rmse[unit]),
                poor_fit=(not is_treated) and float(pre_rmse[unit]) > limit,
                gaps=[
                    s.YearValue(year=int(r.year), value=finite_or_none(r.gap))
                    for r in rows.sort_values(config.COL_YEAR).itertuples(index=False)
                ],
            )
        )
    placebos.sort(key=lambda p: (not p.treated, p.unit_iso3))

    in_time = store.table(config.SC_PLACEBO_TIME_STEM)
    loo = store.table(config.SC_LEAVE_ONE_OUT_STEM)
    loo = loo[(loo[config.COL_OUTCOME] == name) & (loo[config.COL_SERIES] == "synthetic")]
    refits = [
        s.LeaveOneOut(
            dropped_donor=str(donor),
            dropped_name=config.COUNTRIES[str(donor)],
            dropped_name_i18n=_l(config.COUNTRIES[str(donor)]),
            synthetic=[
                s.YearValue(year=int(r.year), value=finite_or_none(r.value))
                for r in rows.sort_values(config.COL_YEAR).itertuples(index=False)
            ],
        )
        for donor, rows in loo.groupby("dropped_donor", sort=True)
    ]
    band = loo.groupby(config.COL_YEAR)[config.COL_VALUE].agg(["min", "max"])
    n_units = int(metrics["n_units"])
    p_value = float(metrics["pseudo_p_value"])
    return s.OutcomeResult(
        outcome=name,
        label=outcome.label,
        label_i18n=_l(outcome.label),
        units=outcome.units,
        units_i18n=_l(outcome.units),
        is_currency=outcome.is_currency,
        credibility=s.SCCredibility(
            credible=credible,
            pre_rmse_share=share,
            threshold=config.SC_CREDIBLE_PRE_RMSE_SHARE,
            message=None if credible else config.SC_NOT_CREDIBLE_MESSAGE,
            message_i18n=None if credible else _l(config.SC_NOT_CREDIBLE_MESSAGE),
        ),
        metrics=s.SCMetrics(
            pre_rmse=float(metrics["pre_rmse"]),
            post_rmse=float(metrics["post_rmse"]),
            rmse_ratio=finite_or_none(metrics["rmse_ratio"]),
            pre_rmse_share=share,
            pseudo_p_value=p_value,
            p_value_floor=1 / n_units,
            rank=round(p_value * n_units),
            n_units=n_units,
            n_effective_donors=float(metrics["n_effective_donors"]),
            n_weighted_donors=int(metrics["n_weighted_donors"]),
            intime_rmse_ratio=finite_or_none(metrics["intime_rmse_ratio"]),
            loo_max_deviation=finite_or_none(metrics["loo_max_deviation"]),
        ),
        series=series,
        latest=latest,
        latest_gap_share=(
            latest.gap / latest.synthetic if latest.gap is not None and latest.synthetic else None
        ),
        weights=[
            s.DonorWeight(
                donor_iso3=r.donor_iso3,
                donor_name=r.donor_name,
                donor_name_i18n=_l(r.donor_name),
                weight=float(r.weight),
            )
            for r in weights.itertuples(index=False)
        ],
        placebos=placebos,
        placebo_time=s.InTimePlacebo(
            placebo_year=config.SC_INTIME_PLACEBO_YEAR,
            series=_sc_points(in_time[in_time[config.COL_OUTCOME] == name]),
        ),
        leave_one_out=refits,
        leave_one_out_band=[
            s.Band(year=int(year), low=float(row["min"]), high=float(row["max"]))
            for year, row in band.iterrows()
        ],
    )


def counterfactual(store: DataStore) -> s.CounterfactualResponse:
    """Every outcome's precomputed synthetic control."""
    return s.CounterfactualResponse(
        treated_country=config.TREATED_COUNTRY,
        treatment_year=config.TREATMENT_YEAR,
        outcomes=[_outcome(store, outcome) for outcome in config.SC_OUTCOMES],
    )


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


def _years() -> list[int]:
    return list(range(config.SD_BACKTEST_START, config.SD_HORIZON_END + 1))


def sd_credibility(store: DataStore) -> s.SDCredibility:
    """The future model's verdicts, from ``sd_metrics`` and ``sd_profile``."""
    metrics = store.table(config.SD_METRICS_STEM)
    by_scope = metrics.set_index(config.COL_SCOPE)
    overall = by_scope.loc["overall"]
    credible = bool(bool_or_none(overall["credible"]))
    index = store.table(config.INDEX_STEM)
    observed = index[
        (index[config.COL_COUNTRY_ISO3] == config.TREATED_COUNTRY)
        & (index[config.COL_SERIES] == config.COMBINED_SERIES)
    ]
    profile = store.table(config.SD_PROFILE_STEM)
    return s.SDCredibility(
        credible=credible,
        overall_nrmse=float(overall["nrmse"]),
        threshold=config.SD_CREDIBLE_NRMSE,
        message=None if credible else config.SD_NOT_CREDIBLE_MESSAGE,
        message_i18n=None if credible else _l(config.SD_NOT_CREDIBLE_MESSAGE),
        framing=config.SCENARIO_FRAMING,
        framing_i18n=_l(config.SCENARIO_FRAMING),
        composition_gap=finite_or_none(by_scope.loc[config.COMBINED_SERIES, "composition_gap"]),
        last_observed_year=int(observed[config.COL_YEAR].max()),
        unidentified=list(sd.UNIDENTIFIED),
        unidentified_labels=[PARAMETER_LABELS.get(n, n) for n in sd.UNIDENTIFIED],
        unidentified_labels_i18n=[_l(PARAMETER_LABELS.get(n, n)) for n in sd.UNIDENTIFIED],
        profile_flat=bool(profile["flat"].map(bool_or_none).all()),
        metrics=[
            s.MetricRow(
                scope=r.scope,
                nrmse=finite_or_none(r.nrmse),
                credible=bool(bool_or_none(r.credible)),
                n_obs=int(r.n_obs),
                composition_gap=finite_or_none(r.composition_gap),
            )
            for r in metrics.itertuples(index=False)
        ],
    )


def _overlap_years(store: DataStore) -> list[int]:
    paths = store.table(config.SC_STEM)
    synthetic = paths[
        (paths[config.COL_SERIES] == "synthetic")
        & (paths[config.COL_YEAR] >= config.TREATMENT_YEAR)
    ]
    return sorted(int(y) for y in set(synthetic[config.COL_YEAR]))


def _matches_counterfactual_over(scenario: Scenario, years: Sequence[int]) -> bool:
    """Whether a scenario is the no-coup path over the overlap.

    Levers apply only from the projection start, after the overlap, so the
    stability path alone decides it - and a scenario that matches is identical
    there, member for member, so the precomputed check is its check.
    """
    reference = config.SCENARIOS[
        [sc.name for sc in config.SCENARIOS].index(config.SD_COUNTERFACTUAL_SCENARIO)
    ]
    if max(years, default=0) >= config.SD_PROJECTION_START:
        return scenario.name == reference.name
    xs = np.asarray(years, dtype=float)

    def recovery(sc: Scenario) -> np.ndarray:
        bx, br = zip(*sc.stability, strict=True)
        return np.interp(xs, bx, br)

    return bool(np.allclose(recovery(scenario), recovery(reference)))


def _sc_checks(store: DataStore, scenario: Scenario) -> list[s.SCCheck]:
    metrics = store.table(config.SD_METRICS_STEM).set_index(config.COL_SCOPE)
    sc_metrics = store.table(config.SC_METRICS_STEM).set_index(config.COL_OUTCOME)
    years = _overlap_years(store)
    applicable = _matches_counterfactual_over(scenario, years)
    checks = []
    for outcome in config.SC_OUTCOMES:
        if outcome.name not in metrics.index:
            continue
        sc_credible = bool(bool_or_none(sc_metrics.loc[outcome.name, "credible"]))
        deviation = consistent = None
        reason: dict[i18n.Locale, str] | None = None
        if not applicable:
            reason = i18n.fill(config.SC_CHECK_OFF_PATH_TEMPLATE, year=years[-1] + 1)
        elif not sc_credible:
            reason = i18n.text(config.SC_CHECK_NOT_CREDIBLE_MESSAGE)
        else:
            deviation = finite_or_none(metrics.loc[outcome.name, "sc_overlap_deviation"])
            consistent = bool_or_none(metrics.loc[outcome.name, "sc_consistent"])
        checks.append(
            s.SCCheck(
                outcome=outcome.name,
                applicable=applicable,
                sc_credible=sc_credible,
                deviation=deviation,
                tolerance=config.SD_SC_TOLERANCE,
                consistent=consistent,
                reason=reason[i18n.Locale.EN] if reason else None,
                reason_i18n=s.Localized(**reason) if reason else None,
            )
        )
    return checks


def _series_block(
    bands: pd.DataFrame, years: list[int]
) -> dict[str, dict[str, list[float | None]]]:
    out: dict[str, dict[str, list[float | None]]] = {}
    for (series, quantile), rows in bands.groupby([config.COL_SERIES, config.COL_QUANTILE]):
        values = rows.set_index(config.COL_YEAR)[config.COL_VALUE].reindex(years)
        out.setdefault(str(series), {})[str(quantile)] = _floats(values.tolist())
    return out


def _gap_block(gaps: pd.DataFrame | None, years: list[int]) -> dict[str, s.GapSeries] | None:
    if gaps is None or gaps.empty:
        return None
    out = {}
    for series, rows in gaps.groupby(config.COL_SERIES):
        rows = rows.set_index(config.COL_YEAR).reindex(years)
        out[str(series)] = s.GapSeries(
            quantiles={q: _floats(rows[q].tolist()) for q in config.SD_QUANTILES},
            share_above=_floats(rows["share_above"].tolist()),
        )
    return out


def scenario_result(
    store: DataStore,
    scenario: Scenario,
    bands: pd.DataFrame,
    gaps: pd.DataFrame | None,
    *,
    custom: bool,
    base: Scenario | None = None,
) -> s.ScenarioResult:
    """One scenario in the shared shape, from tidy bands and a paired-gap table.

    A custom run (``base`` with the user's levers) is labelled from its base, in
    every locale.
    """
    years = _years()
    if custom and base is not None:
        label = i18n.fill(config.CUSTOM_SCENARIO_LABEL, base=i18n.text(base.label))
        description = i18n.fill(
            config.CUSTOM_SCENARIO_DESCRIPTION, base=i18n.text(base.description)
        )
    else:
        label, description = i18n.text(scenario.label), i18n.text(scenario.description)
    return s.ScenarioResult(
        name=scenario.name,
        label=scenario.label,
        label_i18n=s.Localized(**label),
        description=scenario.description,
        description_i18n=s.Localized(**description),
        custom=custom,
        levers=_levers(scenario),
        stability=_stability(scenario),
        diverges_from=sd.divergence_year(scenario),
        series=_series_block(bands, years),
        gaps=_gap_block(gaps, years),
        sc_checks=_sc_checks(store, scenario),
    )


def _history(store: DataStore) -> s.History:
    years = list(range(config.SD_BACKTEST_START, config.SD_BACKTEST_END + 1))
    panel_frame = store.panel
    gdp = (
        panel_frame[
            (panel_frame[config.COL_COUNTRY_ISO3] == config.TREATED_COUNTRY)
            & (panel_frame[config.COL_INDICATOR_ID] == config.SD_OUTPUT_INDICATOR)
        ]
        .set_index(config.COL_YEAR)[config.COL_VALUE]
        .reindex(years)
    )
    index = store.table(config.INDEX_STEM)
    combined = (
        index[
            (index[config.COL_COUNTRY_ISO3] == config.TREATED_COUNTRY)
            & (index[config.COL_SERIES] == config.COMBINED_SERIES)
        ]
        .set_index(config.COL_YEAR)
        .reindex(years)
    )
    return s.History(
        years=years,
        gdp_pc=_floats(gdp.tolist()),
        combined=_floats(combined[config.COL_VALUE].tolist()),
        combined_coverage=_floats(combined[config.COL_COVERAGE].tolist()),
    )


def _sc_overlay(store: DataStore) -> list[s.SCOverlay]:
    paths = store.table(config.SC_STEM)
    sc_metrics = store.table(config.SC_METRICS_STEM).set_index(config.COL_OUTCOME)
    overlays = []
    for outcome in config.SC_OUTCOMES:
        rows = paths[
            (paths[config.COL_OUTCOME] == outcome.name) & (paths[config.COL_SERIES] == "synthetic")
        ].sort_values(config.COL_YEAR)
        overlays.append(
            s.SCOverlay(
                outcome=outcome.name,
                credible=bool(bool_or_none(sc_metrics.loc[outcome.name, "credible"])),
                years=[int(y) for y in rows[config.COL_YEAR]],
                synthetic=_floats(rows[config.COL_VALUE].tolist()),
            )
        )
    return overlays


def scenarios(store: DataStore) -> s.ScenariosResponse:
    """Every precomputed scenario trajectory, with the model's verdicts."""
    trajectory = store.table(config.SD_TRAJECTORY_STEM)
    gaps = store.table(config.SD_GAPS_STEM)
    results = []
    for scenario in config.SCENARIOS:
        bands = trajectory[trajectory[config.COL_SCENARIO] == scenario.name]
        scenario_gaps = gaps[gaps[config.COL_SCENARIO] == scenario.name]
        results.append(
            scenario_result(
                store,
                scenario,
                bands,
                scenario_gaps if not scenario_gaps.empty else None,
                custom=False,
            )
        )
    return s.ScenariosResponse(
        years=_years(),
        projection_start=config.SD_PROJECTION_START,
        quantiles=list(config.SD_QUANTILES),
        credibility=sd_credibility(store),
        history=_history(store),
        sc_overlay=_sc_overlay(store),
        scenarios=results,
    )


def simulated(
    store: DataStore,
    scenario: Scenario,
    result: sd.SimulationResult,
    *,
    custom: bool,
    base: Scenario | None = None,
) -> s.SimulateResponse:
    """A live run in the same shape as a precomputed scenario; ``base`` labels a custom one."""
    return s.SimulateResponse(
        years=_years(),
        projection_start=config.SD_PROJECTION_START,
        quantiles=list(config.SD_QUANTILES),
        baseline=config.SD_BASELINE_SCENARIO,
        credibility=sd_credibility(store),
        result=scenario_result(
            store, scenario, result.bands, result.gaps, custom=custom, base=base
        ),
    )


# --------------------------------------------------------------------------- #
# Historical arc (phase 7)
# --------------------------------------------------------------------------- #

HISTORICAL_UNITS: dict[str, str] = {
    config.GDP_PC_INDICATOR: "constant 2015 US$",
    config.MADDISON_INDICATOR: "2011 int$, PPP",
}
"""Axis units for the money series; the others carry their units in their name."""


HISTORICAL_FRAMING: dict[str, str] = {
    "divergence": config.DIVERGENCE_FRAMING,
    "low_reliability": config.LOW_RELIABILITY_MESSAGE,
    "modeling_window": config.MODELING_WINDOW_MESSAGE,
    "rulers": config.RULERS_MESSAGE,
    "maddison": config.MADDISON_RULER_MESSAGE,
    "chained_level": config.CHAINED_LEVEL_MESSAGE,
    "fiscal_year": config.HISTORICAL_FISCAL_YEAR_MESSAGE,
    "counterfactual_pointer": config.DIVERGENCE_POINTER_MESSAGE,
}
"""The historical view's caveat wording, by the field names of ``HistoricalFraming``."""


def _historical_name(indicator_id: str) -> str:
    if indicator_id == config.MADDISON_INDICATOR:
        return config.MADDISON_INDICATOR_NAME
    if indicator_id in config.INDICATORS_BY_ID:
        return config.INDICATORS_BY_ID[indicator_id].name
    return config.HISTORICAL_EXTRA_CANDIDATES.get(indicator_id, indicator_id)


def _role(iso3: str) -> str:
    if iso3 == config.TREATED_COUNTRY:
        return "treated"
    return "donor" if iso3 in config.DONOR_POOL else "comparator"


def _default_scenario() -> config.DivergenceScenario:
    return next(
        sc for sc in config.DIVERGENCE_SCENARIOS if sc.name == config.DIVERGENCE_DEFAULT_SCENARIO
    )


def historical_indicators(store: DataStore) -> list[str]:
    """Every id ``GET /historical`` accepts: the table's, plus Maddison (empty when absent)."""
    present = list(dict.fromkeys(store.table(config.HISTORICAL_STEM)[config.COL_INDICATOR_ID]))
    return list(dict.fromkeys([*present, config.MADDISON_INDICATOR]))


def default_historical_countries() -> list[str]:
    """Myanmar and the default comparator's units."""
    comparator = config.DIVERGENCE_COMPARATORS[_default_scenario().comparator]
    return [config.TREATED_COUNTRY, *comparator.units]


def default_historical_indicators() -> list[str]:
    """GDP per capita on the WDI spine, plus Maddison when the snapshot holds it."""
    return [config.GDP_PC_INDICATOR, config.MADDISON_INDICATOR]


def _reliability_rules() -> list[s.ReliabilityRule]:
    return [
        s.ReliabilityRule(country_iso3=iso3, standard_from=year)
        for iso3, year in config.RELIABILITY_LOW_BEFORE.items()
    ]


def _events() -> list[s.HistoricalEventMeta]:
    return [
        s.HistoricalEventMeta(year=e.year, label=e.label, label_i18n=_l(e.label))
        for e in config.HISTORICAL_EVENTS
    ]


def historical_meta(store: DataStore) -> s.HistoricalMeta:
    """The historical layer's settings, from config and the snapshot."""
    table = store.table(config.HISTORICAL_STEM)
    present = set(table[config.COL_INDICATOR_ID])
    sources = dict(zip(table[config.COL_INDICATOR_ID], table[config.COL_SOURCE], strict=False))
    default = _default_scenario()
    return s.HistoricalMeta(
        window=s.Window(start=config.HISTORICAL_START, end=config.HISTORICAL_END),
        countries=[
            s.HistoricalCountryMeta(iso3=iso3, name=name, name_i18n=_l(name), role=_role(iso3))
            for iso3, name in config.HISTORICAL_COUNTRIES.items()
        ],
        indicators=[
            s.HistoricalIndicatorMeta(
                id=i,
                name=_historical_name(i),
                name_i18n=_l(_historical_name(i)),
                source=sources.get(
                    i,
                    str(config.HistoricalSource.MADDISON)
                    if i == config.MADDISON_INDICATOR
                    else str(config.HistoricalSource.WB_CONSTANT),
                ),
                units=HISTORICAL_UNITS.get(i, ""),
                units_i18n=_l(HISTORICAL_UNITS[i])
                if i in HISTORICAL_UNITS
                else s.Localized(en="", my=""),
                present=i in present,
            )
            for i in historical_indicators(store)
        ],
        default_indicators=default_historical_indicators(),
        default_countries=default_historical_countries(),
        comparators=[
            s.ComparatorMeta(
                key=key,
                label=comparator.label,
                label_i18n=_l(comparator.label),
                units=list(comparator.units),
                scenario=next(
                    sc.name for sc in config.DIVERGENCE_SCENARIOS if sc.comparator == key
                ),
                default=key == default.comparator,
            )
            for key, comparator in config.DIVERGENCE_COMPARATORS.items()
            if any(sc.comparator == key for sc in config.DIVERGENCE_SCENARIOS)
        ],
        default_comparator=default.comparator,
        divergence_anchor=default.anchor_year,
        sensitivity_anchors=list(config.DIVERGENCE_SENSITIVITY_ANCHORS),
        events=_events(),
        reliability=_reliability_rules(),
        framing=s.HistoricalFraming(**HISTORICAL_FRAMING),
        framing_i18n=s.HistoricalFramingI18n(
            **{key: _l(text) for key, text in HISTORICAL_FRAMING.items()}
        ),
    )


def historical(
    store: DataStore, indicators: Sequence[str], countries: Sequence[str]
) -> s.HistoricalResponse:
    """Historical rows for the requested series, each with its source and reliability."""
    frame = store.table(config.HISTORICAL_STEM)
    frame = frame[
        frame[config.COL_INDICATOR_ID].isin(indicators)
        & frame[config.COL_COUNTRY_ISO3].isin(countries)
    ].sort_values([config.COL_INDICATOR_ID, config.COL_COUNTRY_ISO3, config.COL_YEAR])
    rows = [
        s.HistoricalRow(
            country_iso3=r.country_iso3,
            indicator_id=r.indicator_id,
            year=int(r.year),
            value=finite_or_none(r.value),
            source=str(r.source),
            reliability=str(r.reliability),
        )
        for r in frame.itertuples(index=False)
    ]
    notes = [
        i18n.text(config.LOW_RELIABILITY_MESSAGE),
        i18n.text(config.MODELING_WINDOW_MESSAGE),
        i18n.text(config.RULERS_MESSAGE),
        i18n.text(config.HISTORICAL_FISCAL_YEAR_MESSAGE),
    ]
    if (frame[config.COL_SOURCE] == str(config.HistoricalSource.MADDISON)).any():
        # The citation stays as published; only the ruler note is translated.
        ruler = i18n.text(config.MADDISON_RULER_MESSAGE)
        notes.append({loc: f"{ruler[loc]}: {config.MADDISON_CITATION}." for loc in i18n.LOCALES})
    return s.HistoricalResponse(
        indicators=list(indicators),
        countries=list(countries),
        rows=rows,
        events=_events(),
        modeling_window=s.Window(start=config.MODELING_WINDOW_START, end=config.YEAR_END),
        reliability=_reliability_rules(),
        notes=[note[i18n.Locale.EN] for note in notes],
        notes_i18n=[s.Localized(**note) for note in notes],
    )


def divergence(store: DataStore, comparator: str) -> s.DivergenceResponse:
    """One comparator's divergence scenario: its path, metrics and anchor sensitivity."""
    scenario = next(sc for sc in config.DIVERGENCE_SCENARIOS if sc.comparator == comparator)
    paths = store.table(config.HISTORICAL_DIVERGENCE_STEM)
    paths = paths[paths[config.COL_SCENARIO] == scenario.name].sort_values(config.COL_YEAR)
    metrics = store.table(config.HISTORICAL_DIVERGENCE_METRICS_STEM)
    row = metrics[metrics[config.COL_SCENARIO] == scenario.name].iloc[0]
    sensitivity = store.table(config.HISTORICAL_DIVERGENCE_SENSITIVITY_STEM)
    sensitivity = sensitivity[sensitivity[config.COL_SCENARIO] == scenario.name].sort_values(
        "anchor_year"
    )
    illustrative = bool(paths["scenario_illustrative"].map(bool_or_none).all()) and bool(
        bool_or_none(row["scenario_illustrative"])
    )
    anchor_low = any(
        iso3 == config.TREATED_COUNTRY and scenario.anchor_year < year
        for iso3, year in config.RELIABILITY_LOW_BEFORE.items()
    )
    anchor_note = i18n.fill(
        config.DIVERGENCE_ANCHOR_LOW_TEMPLATE if anchor_low else config.DIVERGENCE_ANCHOR_TEMPLATE,
        year=scenario.anchor_year,
    )
    notes = [
        anchor_note,
        i18n.text(config.CHAINED_LEVEL_MESSAGE),
        i18n.text(config.DIVERGENCE_NO_INFERENCE_MESSAGE),
        i18n.text(config.LOW_RELIABILITY_MESSAGE),
        i18n.text(config.HISTORICAL_FISCAL_YEAR_MESSAGE),
    ]
    return s.DivergenceResponse(
        scenario=scenario.name,
        comparator=comparator,
        comparator_label=config.DIVERGENCE_COMPARATORS[comparator].label,
        comparator_label_i18n=_l(config.DIVERGENCE_COMPARATORS[comparator].label),
        anchor_year=scenario.anchor_year,
        scenario_illustrative=illustrative,
        framing=config.DIVERGENCE_FRAMING,
        framing_i18n=_l(config.DIVERGENCE_FRAMING),
        counterfactual_pointer=config.DIVERGENCE_POINTER_MESSAGE,
        counterfactual_pointer_i18n=_l(config.DIVERGENCE_POINTER_MESSAGE),
        notes=[note[i18n.Locale.EN] for note in notes],
        notes_i18n=[s.Localized(**note) for note in notes],
        series=[
            s.DivergencePoint(
                year=int(r.year),
                actual=finite_or_none(r.actual),
                path=finite_or_none(r.path),
                gap=finite_or_none(r.gap),
                ratio=finite_or_none(r.ratio),
                n_units=int(r.n_units),
                reliability=str(r.reliability),
            )
            for r in paths.itertuples(index=False)
        ],
        metrics=s.DivergenceMetrics(
            anchor_year=int(row["anchor_year"]),
            anchor_value=float(row["anchor_value"]),
            latest_year=int(row["latest_year"]),
            actual_latest=float(row["actual_latest"]),
            path_latest=float(row["path_latest"]),
            gap_latest=float(row["gap_latest"]),
            ratio_latest=float(row["ratio_latest"]),
            actual_growth_pa=float(row["actual_growth_pa"]),
            path_growth_pa=float(row["path_growth_pa"]),
            min_units=int(row["min_units"]),
        ),
        sensitivity=[
            s.DivergenceSensitivity(
                anchor_year=int(r.anchor_year),
                anchor_value=float(r.anchor_value),
                path_latest=float(r.path_latest),
                ratio_latest=float(r.ratio_latest),
                default=bool(bool_or_none(r.default)),
            )
            for r in sensitivity.itertuples(index=False)
        ],
    )

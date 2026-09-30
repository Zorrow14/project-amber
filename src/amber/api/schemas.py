"""Pydantic request and response models.

Every response that carries a modeled series also carries the verdicts the
modeling phases attached to it - ``coverage`` on index rows, ``credibility`` on
the counterfactual and the scenarios, and the phase 3 consistency check - so a
client cannot show a number without its caveat being in the same payload.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from amber import config

__all__ = [
    "CounterfactualResponse",
    "HealthResponse",
    "IndexResponse",
    "MetaResponse",
    "PanelResponse",
    "ScenariosResponse",
    "SimulateRequest",
    "SimulateResponse",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- #
# Health and meta
# --------------------------------------------------------------------------- #


class DataInfo(_Model):
    """Which snapshot is being served."""

    source: str
    built_at: str | None = Field(description="Release build time (UTC); null for processed.")
    commit: str | None


class HealthResponse(_Model):
    """Liveness and data provenance."""

    status: str
    service: str
    version: str
    data: DataInfo


class Framing(_Model):
    """Neutral wording the UI shows verbatim, so captions and API agree."""

    project: str
    scenario: str
    sd_not_credible: str
    sc_not_credible: str
    coverage: str
    fiscal_year: str


class CountryMeta(_Model):
    """One country in the panel."""

    iso3: str
    name: str
    treated: bool
    donor: bool


class IndicatorMeta(_Model):
    """One panel indicator and how the index treats it."""

    id: str
    name: str
    pillar: str
    polarity: str
    in_index: bool
    excluded_reason: str | None
    goalpost_low: float
    goalpost_high: float
    log_scale: bool


class PillarMeta(_Model):
    """One index pillar."""

    id: str
    label: str
    default_weight: float


class LeverMeta(_Model):
    """One policy lever - everything a slider needs."""

    name: str
    label: str
    description: str
    min: float
    max: float
    step: float
    default: float


class StabilityPoint(_Model):
    """A breakpoint of a scenario's stability-recovery path (1 = reform era)."""

    year: int
    recovery: float


class ScenarioMeta(_Model):
    """One configured scenario."""

    name: str
    label: str
    description: str
    levers: dict[str, float] = Field(description="Every lever, defaults filled in.")
    stability: list[StabilityPoint]
    diverges_from: int | None = Field(description="First year it differs from history.")


class OutcomeMeta(_Model):
    """One synthetic-control outcome."""

    id: str
    label: str
    units: str
    is_currency: bool


class SeriesMeta(_Model):
    """One series in a scenario trajectory."""

    id: str
    label: str
    kind: str = Field(description="stock, indicator, pillar or combined")


class Window(_Model):
    """An inclusive year range."""

    start: int
    end: int


class Thresholds(_Model):
    """The credibility gates, so the UI can state them."""

    sc_credible_pre_rmse_share: float
    sc_placebo_poor_fit_multiple: float
    sd_credible_nrmse: float
    sd_sc_tolerance: float
    sd_profile_tolerance: float


class MetaResponse(_Model):
    """Everything the frontend needs so that it hardcodes nothing."""

    framing: Framing
    treated_country: str
    countries: list[CountryMeta]
    indicators: list[IndicatorMeta]
    pillars: list[PillarMeta]
    normalizations: list[str]
    default_normalization: str
    treatment_year: int
    modeling_window: Window
    covid_years: list[int]
    projection_start: int
    horizon_end: int
    levers: list[LeverMeta]
    scenarios: list[ScenarioMeta]
    baseline_scenario: str
    counterfactual_scenario: str
    quantiles: list[str]
    ensemble_size: int
    sc_outcomes: list[OutcomeMeta]
    sd_series: list[SeriesMeta]
    thresholds: Thresholds
    data: DataInfo


# --------------------------------------------------------------------------- #
# Panel and index
# --------------------------------------------------------------------------- #


class PanelRow(_Model):
    """One country-indicator-year observation."""

    country_iso3: str
    indicator_id: str
    year: int
    value: float | None
    imputed: bool = Field(description="Interpolated across an interior gap, not observed.")


class SeriesCoverage(_Model):
    """How far a country's series runs, from the coverage report."""

    country_iso3: str
    indicator_id: str
    last_year_observed: int | None
    is_dark: bool = Field(description="Stops reporting before the treatment year.")


class PanelResponse(_Model):
    """Tidy indicator series for the descriptive charts."""

    indicators: list[str]
    countries: list[str]
    rows: list[PanelRow]
    coverage: list[SeriesCoverage]


class IndexRow(_Model):
    """One pillar or combined score."""

    country_iso3: str
    country_name: str
    year: int
    series: str
    value: float
    coverage: float = Field(description="Share of the series' indicators observed; < 1 is partial.")


class IndexResponse(_Model):
    """The index recomputed live under the requested weights."""

    method: str
    weights: dict[str, float] = Field(description="As applied, renormalized to sum to 1.")
    computed_live: bool
    coverage_note: str
    rows: list[IndexRow]


# --------------------------------------------------------------------------- #
# Counterfactual
# --------------------------------------------------------------------------- #


class SCCredibility(_Model):
    """Whether an outcome's synthetic control is an estimate at all."""

    credible: bool
    pre_rmse_share: float
    threshold: float
    message: str | None = Field(description="Set when not credible; show it prominently.")


class SCMetrics(_Model):
    """Fit and inference diagnostics, as in ``sc_metrics``."""

    pre_rmse: float
    post_rmse: float
    rmse_ratio: float | None
    pre_rmse_share: float
    pseudo_p_value: float
    p_value_floor: float = Field(description="1 / units: the smallest p-value possible here.")
    rank: int = Field(description="Myanmar's post/pre ratio rank among all units (1 = largest).")
    n_units: int
    n_effective_donors: float
    n_weighted_donors: int
    intime_rmse_ratio: float | None
    loo_max_deviation: float | None


class SCPoint(_Model):
    """Actual, synthetic and gap in one year."""

    year: int
    actual: float | None
    synthetic: float | None
    gap: float | None


class YearValue(_Model):
    """A value in a year."""

    year: int
    value: float | None


class DonorWeight(_Model):
    """One donor's weight in synthetic Myanmar."""

    donor_iso3: str
    donor_name: str
    weight: float


class Placebo(_Model):
    """One unit's gap when treated as if it had been treated in 2021."""

    unit_iso3: str
    unit_name: str
    treated: bool
    pre_rmse: float
    poor_fit: bool = Field(description="Pre-RMSE beyond the poor-fit multiple of Myanmar's.")
    gaps: list[YearValue]


class InTimePlacebo(_Model):
    """The fit re-run with a fake treatment year."""

    placebo_year: int
    series: list[SCPoint]


class LeaveOneOut(_Model):
    """Synthetic Myanmar refitted without one weighted donor."""

    dropped_donor: str
    dropped_name: str
    synthetic: list[YearValue]


class Band(_Model):
    """A low-high band by year."""

    year: int
    low: float
    high: float


class OutcomeResult(_Model):
    """The whole counterfactual for one outcome."""

    outcome: str
    label: str
    units: str
    is_currency: bool
    credibility: SCCredibility
    metrics: SCMetrics
    series: list[SCPoint]
    latest: SCPoint
    latest_gap_share: float | None = Field(description="Latest gap over the synthetic value.")
    weights: list[DonorWeight]
    placebos: list[Placebo]
    placebo_time: InTimePlacebo
    leave_one_out: list[LeaveOneOut]
    leave_one_out_band: list[Band]


class CounterfactualResponse(_Model):
    """Precomputed synthetic-control results for every outcome."""

    treated_country: str
    treatment_year: int
    outcomes: list[OutcomeResult]


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


class SCCheck(_Model):
    """How a scenario compares with the phase 3 synthetic control over the overlap."""

    outcome: str
    applicable: bool
    sc_credible: bool
    deviation: float | None = Field(description="Largest relative gap over the overlap years.")
    tolerance: float
    consistent: bool | None
    reason: str | None = Field(description="Why no deviation is reported, when it is not.")


class GapSeries(_Model):
    """The paired, member-by-member gap from the baseline for one series."""

    quantiles: dict[str, list[float | None]]
    share_above: list[float | None]


class ScenarioResult(_Model):
    """One scenario's ensemble trajectory."""

    name: str
    label: str
    description: str
    custom: bool
    levers: dict[str, float]
    stability: list[StabilityPoint]
    diverges_from: int | None
    series: dict[str, dict[str, list[float | None]]] = Field(
        description="Series -> quantile -> values aligned to ``years``."
    )
    gaps: dict[str, GapSeries] | None = Field(description="Null for the baseline itself.")
    sc_checks: list[SCCheck]


class MetricRow(_Model):
    """One scope of the backtest (``sd_metrics``)."""

    scope: str
    nrmse: float | None
    credible: bool
    n_obs: int
    composition_gap: float | None


class SDCredibility(_Model):
    """The future model's verdicts - shown with every trajectory."""

    credible: bool
    overall_nrmse: float
    threshold: float
    message: str | None = Field(description="Set when not credible; show it prominently.")
    framing: str
    composition_gap: float | None = Field(
        description="Step between history's reported indicators and the model's full set."
    )
    last_observed_year: int
    unidentified: list[str]
    unidentified_labels: list[str]
    profile_flat: bool
    metrics: list[MetricRow]


class History(_Model):
    """What actually happened, for the lines the fan starts from."""

    years: list[int]
    gdp_pc: list[float | None]
    combined: list[float | None]
    combined_coverage: list[float | None]


class SCOverlay(_Model):
    """A phase 3 synthetic path to draw over the overlap, where credible."""

    outcome: str
    credible: bool
    years: list[int]
    synthetic: list[float | None]


class ScenariosResponse(_Model):
    """Every precomputed scenario."""

    years: list[int]
    projection_start: int
    quantiles: list[str]
    credibility: SDCredibility
    history: History
    sc_overlay: list[SCOverlay]
    scenarios: list[ScenarioResult]


class SimulateRequest(_Model):
    """A scenario to run live: a configured one, optionally with lever overrides.

    Levers alone do not define a future - the stability path does - so
    ``levers`` override the named scenario (default: actual continuation).
    """

    scenario: str | None = Field(default=None, description="Base scenario name.")
    levers: dict[str, float] = Field(default_factory=dict, description="Lever overrides.")

    @model_validator(mode="after")
    def _known_and_in_range(self) -> SimulateRequest:
        names = [s.name for s in config.SCENARIOS]
        if self.scenario is not None and self.scenario not in names:
            msg = f"Unknown scenario {self.scenario!r}; expected one of {names}"
            raise ValueError(msg)
        unknown = sorted(set(self.levers) - set(config.LEVERS))
        if unknown:
            msg = f"Unknown levers {unknown}; expected any of {sorted(config.LEVERS)}"
            raise ValueError(msg)
        for name, value in self.levers.items():
            lever = config.LEVERS[name]
            if not lever.low <= value <= lever.high:
                msg = f"Lever {name}={value} is outside its range [{lever.low}, {lever.high}]"
                raise ValueError(msg)
        return self


class SimulateResponse(_Model):
    """A live scenario run, on the precomputed calibration."""

    years: list[int]
    projection_start: int
    quantiles: list[str]
    baseline: str
    credibility: SDCredibility
    result: ScenarioResult

"""Synthetic-control counterfactual - phase 3.

For a treated unit (Myanmar) and a treatment year (2021), build a *synthetic*
Myanmar as a convex combination of donor countries that best tracks the real one
before treatment. After treatment, actual minus synthetic is the estimated
effect (Abadie, Diamond & Hainmueller 2010).

**Objective.** Features are the pre-treatment outcome path - one feature per fit
year - plus the fit-window mean of any configured covariates, each z-scored
across the treated unit and its donors. With V = identity, the weights solve::

    min_w  || x1 - X0 w ||^2    subject to  w_j >= 0,  sum_j w_j = 1

The simplex constraint is what makes this synthetic control rather than
regression: the counterfactual is an interpolation *inside* the donor hull,
never an extrapolation beyond it. It is solved with SLSQP from several seeded
starts, keeping the best, so a run is deterministic.

**What to read in the output.** ``pre_rmse`` is the credibility check: if the
treated unit sits outside the donor hull the fit is poor, and a poor pre-fit
means the post-treatment gap cannot be read as an effect. ``rmse_ratio``
(post / pre) is what the in-space placebo ranks.

**The 2020 tension.** The fit window runs to 2020 by default
(:data:`~amber.config.SC_PRE_PERIOD_END`). Elsewhere 2020 is treated as
COVID-confounded - rightly, when the question is attributing a shock to the coup.
Here the question is what donors share, and COVID hit them too, so keeping 2020
matches against donors that also absorbed it. The cost: Myanmar's WDI 2020
(fiscal Oct 2019-Sep 2020, pre-coup) records -9.1% growth, below every donor,
so no convex combination reaches it. Refit with the window ending 2019 to see
how much that one year moves the estimate.

**Inference** (:func:`run_placebo_space`) is by permutation, so it is coarse by
construction: with N units the smallest attainable p-value is 1/N - 1/7 for
Myanmar and six donors. Ranking first is the strongest result available.

Future work: nested optimisation of V (predictor importance), which six donors
cannot support without overfitting.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from amber import config
from amber.config import SCOutcome

logger = logging.getLogger(__name__)

__all__ = [
    "CounterfactualRun",
    "PlaceboSpaceResult",
    "SCSettings",
    "SyntheticControlResult",
    "fit_synthetic_control",
    "leave_one_out",
    "loo_max_deviation",
    "outcome_matrix",
    "resolve_outcome_source",
    "run",
    "run_placebo_space",
    "run_placebo_time",
]

_ZERO_RMSE = 1e-12
"""A pre-RMSE below this is a perfect fit; its ratio is reported as infinite."""


# --------------------------------------------------------------------------- #
# Settings and results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SCSettings:
    """Everything a fit depends on besides the data, defaulted from config.

    Shared by the base fit, placebos and leave-one-out refits, so they cannot
    silently diverge.

    Attributes:
        treatment_year: First post-treatment year.
        pre_start: First fit year (inclusive).
        pre_end: Last fit year (inclusive).
        predictors: Covariate indicator ids averaged over the fit window.
        rebase: Index each series to 100 at ``pre_start`` before matching.
        n_restarts: SLSQP starts per fit.
        seed: RNG seed for the restart draws.
        min_donors: Fewest complete donors a fit may use.
        weight_threshold: Weight at which a donor counts as positively weighted.
    """

    treatment_year: int = config.TREATMENT_YEAR
    pre_start: int = config.MODELING_WINDOW_START
    pre_end: int = config.SC_PRE_PERIOD_END
    predictors: tuple[str, ...] = config.SC_PREDICTORS
    rebase: bool = config.SC_REBASE
    n_restarts: int = config.SC_N_RESTARTS
    seed: int = config.SC_SEED
    min_donors: int = config.SC_MIN_DONORS
    weight_threshold: float = config.SC_WEIGHT_THRESHOLD

    @property
    def fit_years(self) -> range:
        """The fit window as a range of years."""
        return range(self.pre_start, self.pre_end + 1)


@dataclass(frozen=True, slots=True)
class SyntheticControlResult:
    """One fitted synthetic control.

    Attributes:
        outcome: The outcome's name.
        treated: ISO3 of the (possibly pseudo-) treated unit.
        settings: The settings the fit used.
        weights: Donor ISO3 -> weight over every donor in the fit; sums to 1.
        actual: Treated unit's outcome by year.
        synthetic: The weighted donor combination by year.
        gap: ``actual - synthetic`` by year.
        pre_rmse: Fit error over the fit window, in outcome units.
        post_rmse: Error from the treatment year on, in outcome units.
        rmse_ratio: ``post_rmse / pre_rmse`` - infinite for a perfect pre-fit.
        dropped_donors: Donors excluded for missing data in the fit window.
        loss: Minimized standardized objective.
    """

    outcome: str
    treated: str
    settings: SCSettings
    weights: dict[str, float]
    actual: pd.Series
    synthetic: pd.Series
    gap: pd.Series
    pre_rmse: float
    post_rmse: float
    rmse_ratio: float
    dropped_donors: tuple[str, ...] = ()
    loss: float = float("nan")

    @property
    def donors(self) -> tuple[str, ...]:
        """Donors the fit used, in weight order."""
        return tuple(self.weights)

    @property
    def n_effective_donors(self) -> float:
        """Effective number of donors, ``1 / sum(w^2)``.

        1.0 when one donor carries everything; ``k`` when ``k`` donors share
        equally. More informative than a count of non-zero weights.
        """
        return 1.0 / sum(w * w for w in self.weights.values())

    def positive_donors(self, threshold: float | None = None) -> tuple[str, ...]:
        """Donors whose weight reaches ``threshold`` (default: the settings')."""
        cut = self.settings.weight_threshold if threshold is None else threshold
        return tuple(d for d, w in self.weights.items() if w >= cut)

    @property
    def pre_rmse_share(self) -> float:
        """Pre-RMSE as a share of the treated unit's mean absolute fit-window level.

        Makes fit quality comparable across outcomes on different scales: $33 on
        a ~$1,200 series is a close fit; 0.07 on a ~0.3 index is not.
        """
        level = self.actual.reindex(self.settings.fit_years).abs().mean()
        return float(self.pre_rmse / level) if level else float("nan")

    @property
    def poor_fit(self) -> bool:
        """Whether the pre-fit is too loose to read the gap as an effect."""
        return self.pre_rmse_share > config.SC_POOR_FIT_SHARE


@dataclass(frozen=True, slots=True)
class PlaceboSpaceResult:
    """In-space placebo: every donor refitted as if it had been treated.

    Attributes:
        treated: The real fit.
        placebos: Donor ISO3 -> its placebo fit against the other donors.
        skipped: Donors whose placebo could not be fitted.
    """

    treated: SyntheticControlResult
    placebos: dict[str, SyntheticControlResult]
    skipped: tuple[str, ...] = ()

    @property
    def ratios(self) -> pd.Series:
        """Post/pre RMSE ratio for the treated unit and every placebo."""
        ratios = {self.treated.treated: self.treated.rmse_ratio}
        ratios.update({unit: fit.rmse_ratio for unit, fit in self.placebos.items()})
        return pd.Series(ratios, name="rmse_ratio")

    @property
    def p_value(self) -> float:
        """Share of units whose ratio is at least the treated unit's.

        The treated unit counts itself, so this lies in (0, 1] and bottoms out
        at 1 / (placebos + 1).
        """
        ratios = self.ratios
        return float((ratios >= ratios[self.treated.treated]).sum() / len(ratios))


@dataclass(frozen=True, slots=True)
class CounterfactualRun:
    """Everything estimated for one outcome.

    Attributes:
        outcome: The outcome definition.
        base: The fit for the real treated unit.
        placebo_space: In-space placebo inference.
        placebo_time: In-time placebo, or ``None`` if it could not be fitted.
        leave_one_out: Dropped donor ISO3 -> refit without it.
    """

    outcome: SCOutcome
    base: SyntheticControlResult
    placebo_space: PlaceboSpaceResult
    placebo_time: SyntheticControlResult | None
    leave_one_out: dict[str, SyntheticControlResult] = field(default_factory=dict)

    @property
    def p_value(self) -> float:
        """The headline pseudo p-value."""
        return self.placebo_space.p_value

    @property
    def loo_max_deviation(self) -> float:
        """Largest post-period move in the synthetic from dropping one donor."""
        return loo_max_deviation(self.base, self.leave_one_out)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def resolve_outcome_source(name: str) -> Literal["panel", "index"]:
    """Say whether an outcome is read from the panel or from the index.

    Args:
        name: A WDI indicator id or an index series name.

    Returns:
        ``"panel"`` or ``"index"``.

    Raises:
        ValueError: If the name is in neither.
    """
    if name in config.INDICATORS_BY_ID:
        return "panel"
    if name in config.INDEX_SERIES:
        return "index"
    msg = f"Outcome {name!r} is neither a configured indicator nor an index series"
    raise ValueError(msg)


def outcome_matrix(
    name: str,
    *,
    panel: pd.DataFrame | None = None,
    index: pd.DataFrame | None = None,
    start: int = config.MODELING_WINDOW_START,
) -> pd.DataFrame:
    """Pivot an outcome into years x countries.

    Args:
        name: A WDI indicator id (read from ``panel``) or an index series name
            (read from ``index``).
        panel: Tidy panel, needed for indicator outcomes.
        index: Tidy index table, needed for index outcomes.
        start: First year kept.

    Returns:
        A frame indexed by year with one column per configured country.

    Raises:
        ValueError: If the source the outcome needs was not supplied.
    """
    source = resolve_outcome_source(name)
    if source == "panel":
        if panel is None:
            msg = f"Outcome {name!r} is a WDI indicator; pass the panel"
            raise ValueError(msg)
        rows = panel[panel[config.COL_INDICATOR_ID] == name]
    else:
        if index is None:
            msg = f"Outcome {name!r} is an index series; pass index.csv"
            raise ValueError(msg)
        rows = index[index[config.COL_SERIES] == name]

    wide = rows.pivot_table(
        index=config.COL_YEAR,
        columns=config.COL_COUNTRY_ISO3,
        values=config.COL_VALUE,
        aggfunc="first",
    )
    wide = wide.reindex(columns=[c for c in config.COUNTRY_CODES if c in wide.columns])
    wide = wide.loc[wide.index >= start].sort_index()
    wide.columns.name = None
    wide.name = name
    return wide.astype(float)


def _predictor_means(
    covariates: pd.DataFrame,
    predictors: Sequence[str],
    units: Sequence[str],
    years: range,
) -> pd.DataFrame:
    """Average each covariate over the fit window, per unit (units x predictors)."""
    rows = covariates[
        covariates[config.COL_INDICATOR_ID].isin(predictors)
        & covariates[config.COL_COUNTRY_ISO3].isin(units)
        & covariates[config.COL_YEAR].between(years.start, years.stop - 1)
    ]
    means = rows.pivot_table(
        index=config.COL_COUNTRY_ISO3,
        columns=config.COL_INDICATOR_ID,
        values=config.COL_VALUE,
        aggfunc="mean",
    )
    return means.reindex(index=list(units), columns=list(predictors))


# --------------------------------------------------------------------------- #
# Fitting
# --------------------------------------------------------------------------- #


def _standardize(features: pd.DataFrame) -> pd.DataFrame:
    """Z-score each feature across units, dropping features with no spread.

    A constant feature carries no information - rebasing makes the base year
    exactly 100 for everyone - and would divide by zero.
    """
    mean = features.mean(axis=0)
    std = features.std(axis=0, ddof=0)
    informative = std > 0
    if not informative.all():
        logger.debug("Dropping %d features with no spread", int((~informative).sum()))
    if not informative.any():
        msg = "No feature varies across units; the fit is undefined"
        raise ValueError(msg)
    return (features.loc[:, informative] - mean[informative]) / std[informative]


def _solve_weights(
    x1: np.ndarray,
    x0: np.ndarray,
    n_restarts: int,
    seed: int,
) -> tuple[np.ndarray, float]:
    """Minimize ``||x1 - x0 @ w||^2`` over the simplex.

    Args:
        x1: Treated unit's standardized features, shape (k,).
        x0: Donors' standardized features, shape (k, J).
        n_restarts: Starts to try: uniform first, then Dirichlet draws.
        seed: RNG seed for the draws.

    Returns:
        The best weights (non-negative, summing to 1) and their loss.
    """
    n_donors = x0.shape[1]

    def loss(w: np.ndarray) -> float:
        residual = x0 @ w - x1
        return float(residual @ residual)

    def grad(w: np.ndarray) -> np.ndarray:
        return 2.0 * x0.T @ (x0 @ w - x1)

    constraint = {
        "type": "eq",
        "fun": lambda w: float(w.sum() - 1.0),
        "jac": lambda w: np.ones_like(w),
    }
    rng = np.random.default_rng(seed)
    starts = [np.full(n_donors, 1.0 / n_donors)]
    starts += [rng.dirichlet(np.ones(n_donors)) for _ in range(n_restarts - 1)]

    best_w, best_loss = starts[0], math.inf
    for start in starts:
        result = minimize(
            loss,
            start,
            jac=grad,
            method="SLSQP",
            bounds=[(0.0, 1.0)] * n_donors,
            constraints=[constraint],
            options={"ftol": 1e-12, "maxiter": 1000},
        )
        if result.fun < best_loss:
            best_w, best_loss = result.x, float(result.fun)

    # SLSQP can land a hair outside the simplex; project back onto it.
    weights = np.clip(best_w, 0.0, None)
    weights /= weights.sum()
    return weights, loss(weights)


def _rmse(values: pd.Series) -> float:
    values = values.dropna()
    return float(np.sqrt(np.mean(np.square(values)))) if len(values) else float("nan")


def fit_synthetic_control(
    outcome: pd.DataFrame,
    *,
    treated: str = config.TREATED_COUNTRY,
    donors: Sequence[str] = tuple(config.DONOR_POOL),
    settings: SCSettings | None = None,
    covariates: pd.DataFrame | None = None,
    name: str | None = None,
) -> SyntheticControlResult:
    """Fit a synthetic control for one treated unit.

    Args:
        outcome: Years x units, from :func:`outcome_matrix`.
        treated: ISO3 of the treated unit.
        donors: ISO3s of candidate donors. Any missing outcome (or covariate)
            data in the fit window is dropped, with a warning.
        settings: Fit settings; defaults to config.
        covariates: Tidy panel, required only if ``settings.predictors`` is set.
        name: Outcome name for the result; defaults to ``outcome.name``.

    Returns:
        The fitted result.

    Raises:
        ValueError: If the treated unit lacks data in the fit window, fewer than
            ``min_donors`` donors are complete, predictors are requested without
            covariates, or rebasing hits a non-positive base value.
    """
    settings = settings or SCSettings()
    label = name or getattr(outcome, "name", None) or "outcome"
    years = settings.fit_years
    donors = [d for d in donors if d != treated]

    if treated not in outcome.columns or outcome[treated].reindex(years).isna().any():
        msg = f"{treated} is missing {label} in the fit window {years.start}-{years.stop - 1}"
        raise ValueError(msg)

    window = outcome.reindex(years)
    complete = [d for d in donors if d in outcome.columns and window[d].notna().all()]

    predictors = pd.DataFrame(index=[treated, *complete])
    if settings.predictors:
        if covariates is None:
            msg = "SC predictors are configured but no covariate panel was passed"
            raise ValueError(msg)
        predictors = _predictor_means(covariates, settings.predictors, [treated, *complete], years)
        if predictors.loc[treated].isna().any():
            msg = f"{treated} is missing predictor data in the fit window"
            raise ValueError(msg)
        complete = [d for d in complete if predictors.loc[d].notna().all()]

    dropped = tuple(d for d in donors if d not in complete)
    if dropped:
        logger.warning(
            "%s: dropping donors with incomplete data for %s: %s", treated, label, dropped
        )
    if len(complete) < settings.min_donors:
        msg = (
            f"{treated}/{label}: only {len(complete)} complete donors "
            f"({complete}); at least {settings.min_donors} are required"
        )
        raise ValueError(msg)

    series = outcome[[treated, *complete]]
    if settings.rebase:
        base = series.loc[settings.pre_start]
        if (base <= 0).any() or base.isna().any():
            msg = f"Cannot rebase {label}: base-year values must be positive"
            raise ValueError(msg)
        series = series / base * 100.0

    features = pd.concat([series.loc[list(years)].T, predictors.loc[series.columns]], axis=1)
    features.columns = features.columns.astype(str)
    standardized = _standardize(features)

    weights, loss = _solve_weights(
        standardized.loc[treated].to_numpy(),
        standardized.loc[complete].to_numpy().T,
        settings.n_restarts,
        settings.seed,
    )

    donor_series = series[complete]
    used = weights > 0
    # A year gets a synthetic value only if every donor that carries weight is
    # observed then - reweighting over whoever happens to report would be a
    # different synthetic unit.
    observed = donor_series.loc[:, used].notna().all(axis=1)
    synthetic = (donor_series.fillna(0.0) @ weights).where(observed)
    actual = series[treated]
    gap = actual - synthetic

    pre_rmse = _rmse(gap.reindex(years))
    post_rmse = _rmse(gap.loc[gap.index >= settings.treatment_year])
    ratio = math.inf if pre_rmse < _ZERO_RMSE else post_rmse / pre_rmse

    ordered = dict(sorted(zip(complete, weights.tolist(), strict=True), key=lambda kv: -kv[1]))
    logger.info(
        "%s/%s: pre-RMSE %.4g, post-RMSE %.4g, weights %s",
        treated,
        label,
        pre_rmse,
        post_rmse,
        {d: round(w, 3) for d, w in ordered.items() if w >= settings.weight_threshold},
    )
    return SyntheticControlResult(
        outcome=label,
        treated=treated,
        settings=settings,
        weights=ordered,
        actual=actual.rename("actual"),
        synthetic=synthetic.rename("synthetic"),
        gap=gap.rename("gap"),
        pre_rmse=pre_rmse,
        post_rmse=post_rmse,
        rmse_ratio=ratio,
        dropped_donors=dropped,
        loss=loss,
    )


# --------------------------------------------------------------------------- #
# Inference and robustness
# --------------------------------------------------------------------------- #


def run_placebo_space(
    outcome: pd.DataFrame,
    base: SyntheticControlResult,
    *,
    covariates: pd.DataFrame | None = None,
) -> PlaceboSpaceResult:
    """Refit with each donor as the pseudo-treated unit.

    Each placebo is matched against the *other* donors only - the real treated
    unit is never a donor, or its post-treatment break would leak into every
    placebo. The p-value then asks how unusual the treated unit's post/pre
    RMSE ratio is among all units.

    Args:
        outcome: Years x units, from :func:`outcome_matrix`.
        base: The fit for the real treated unit; its donors and settings are
            reused.
        covariates: Tidy panel, if predictors are configured.

    Returns:
        The placebo fits and the resulting p-value.
    """
    placebos: dict[str, SyntheticControlResult] = {}
    skipped: list[str] = []
    for unit in base.donors:
        others = [d for d in base.donors if d != unit]
        try:
            placebos[unit] = fit_synthetic_control(
                outcome,
                treated=unit,
                donors=others,
                settings=base.settings,
                covariates=covariates,
                name=base.outcome,
            )
        except ValueError as exc:
            logger.warning("Skipping placebo for %s: %s", unit, exc)
            skipped.append(unit)

    result = PlaceboSpaceResult(treated=base, placebos=placebos, skipped=tuple(skipped))
    logger.info(
        "%s: in-space placebo p = %.3f over %d units (floor %.3f)",
        base.outcome,
        result.p_value,
        len(placebos) + 1,
        1 / (len(placebos) + 1),
    )
    return result


def run_placebo_time(
    outcome: pd.DataFrame,
    base: SyntheticControlResult,
    *,
    placebo_year: int = config.SC_INTIME_PLACEBO_YEAR,
    covariates: pd.DataFrame | None = None,
) -> SyntheticControlResult:
    """Refit as if treatment had happened earlier, using only pre-treatment data.

    Data from the real treatment year on is discarded, so the fake post-period
    (``placebo_year`` to the year before treatment) is genuinely untreated. A
    good design shows a gap near zero there; a large one means the synthetic
    was never tracking and a post-2021 gap would be unreliable too.

    Args:
        outcome: Years x units, from :func:`outcome_matrix`.
        base: The real fit; its treated unit, donors and settings are reused.
        placebo_year: The fake treatment year.
        covariates: Tidy panel, if predictors are configured.

    Returns:
        The in-time placebo fit.

    Raises:
        ValueError: If ``placebo_year`` leaves fewer than two fit years or is not
            before the real treatment year.
    """
    settings = base.settings
    if not settings.pre_start + 1 < placebo_year < settings.treatment_year:
        msg = f"Placebo year {placebo_year} must leave two fit years and precede treatment"
        raise ValueError(msg)

    truncated = outcome.loc[outcome.index < settings.treatment_year]
    fake = replace(settings, treatment_year=placebo_year, pre_end=placebo_year - 1)
    return fit_synthetic_control(
        truncated,
        treated=base.treated,
        donors=base.donors,
        settings=fake,
        covariates=covariates,
        name=base.outcome,
    )


def leave_one_out(
    outcome: pd.DataFrame,
    base: SyntheticControlResult,
    *,
    covariates: pd.DataFrame | None = None,
) -> dict[str, SyntheticControlResult]:
    """Refit once without each positively-weighted donor.

    If the counterfactual hinges on a single donor, dropping it moves the
    synthetic a lot; the spread of these refits is a robustness band.

    Args:
        outcome: Years x units, from :func:`outcome_matrix`.
        base: The real fit.
        covariates: Tidy panel, if predictors are configured.

    Returns:
        Dropped donor ISO3 -> the refit without it. Donors whose removal leaves
        too few others are skipped with a warning.
    """
    refits: dict[str, SyntheticControlResult] = {}
    for donor in base.positive_donors():
        try:
            refits[donor] = fit_synthetic_control(
                outcome,
                treated=base.treated,
                donors=[d for d in base.donors if d != donor],
                settings=base.settings,
                covariates=covariates,
                name=base.outcome,
            )
        except ValueError as exc:
            logger.warning("Skipping leave-one-out without %s: %s", donor, exc)
    return refits


def loo_max_deviation(
    base: SyntheticControlResult,
    refits: Mapping[str, SyntheticControlResult],
) -> float:
    """Largest absolute post-period gap between any refit and the base synthetic.

    Args:
        base: The real fit.
        refits: Output of :func:`leave_one_out`.

    Returns:
        The maximum deviation in outcome units, or NaN with no refits.
    """
    post = base.synthetic.index >= base.settings.treatment_year
    deviations = [
        (refit.synthetic - base.synthetic).loc[post].abs().max() for refit in refits.values()
    ]
    deviations = [d for d in deviations if pd.notna(d)]
    return float(max(deviations)) if deviations else float("nan")


# --------------------------------------------------------------------------- #
# One outcome, end to end
# --------------------------------------------------------------------------- #


def run(
    outcome: SCOutcome | str,
    *,
    panel: pd.DataFrame | None = None,
    index: pd.DataFrame | None = None,
    settings: SCSettings | None = None,
    placebo_year: int = config.SC_INTIME_PLACEBO_YEAR,
) -> CounterfactualRun:
    """Fit, test and stress one outcome.

    Args:
        outcome: An :class:`~amber.config.SCOutcome`, or the name of a
            configured one.
        panel: Tidy panel - the source for indicator outcomes and covariates.
        index: Tidy index table - the source for index outcomes.
        settings: Fit settings; defaults to config.
        placebo_year: Fake treatment year for the in-time placebo.

    Returns:
        The base fit, in-space and in-time placebos, and leave-one-out refits.

    Raises:
        ValueError: If a name matches no configured outcome, or the base fit
            cannot be estimated.
    """
    if isinstance(outcome, str):
        matches = [o for o in config.SC_OUTCOMES if o.name == outcome]
        if not matches:
            msg = f"No configured SC outcome named {outcome!r}"
            raise ValueError(msg)
        outcome = matches[0]

    settings = settings or SCSettings()
    matrix = outcome_matrix(outcome.name, panel=panel, index=index, start=settings.pre_start)
    base = fit_synthetic_control(matrix, settings=settings, covariates=panel, name=outcome.name)

    placebo_space = run_placebo_space(matrix, base, covariates=panel)
    try:
        placebo_time: SyntheticControlResult | None = run_placebo_time(
            matrix, base, placebo_year=placebo_year, covariates=panel
        )
    except ValueError as exc:
        logger.warning("%s: in-time placebo not fitted: %s", outcome.name, exc)
        placebo_time = None
    refits = leave_one_out(matrix, base, covariates=panel)

    return CounterfactualRun(
        outcome=outcome,
        base=base,
        placebo_space=placebo_space,
        placebo_time=placebo_time,
        leave_one_out=refits,
    )

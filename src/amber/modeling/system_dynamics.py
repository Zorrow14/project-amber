"""System-dynamics future model - phase 4.

An annual stock-and-flow model of Myanmar, calibrated on 2011-2024 and run
forward to explore *scenarios* - never forecasts.

**Engine.** A hand-written difference-equation simulator in numpy, not PySD. The
project plan named PySD; this is a deliberate deviation. The rest of Amber is
config-driven pure Python with offline unit tests, and an explicit step function
keeps every equation inspectable and testable with no external Vensim/XMILE
model file to keep in sync with the code.

**Stocks.** Physical capital K, human capital H (life expectancy relative to the
first year, H0 = 1), connectivity I (internet users, % of population) and
institutional stability S (0-1, exogenous - set by the scenario).

**Equations** (annual; parameters in :data:`~amber.config.SD_PARAMETERS`)::

    Y_t     = A0 (1+g)^(t-t0) (1 - c rho^(t-t_c) [t >= t_c]) S_t^gamma (1 + kappa I_t/I_max)
              * K_t^alpha H_t^beta
    K_t+1   = K_t + s_K fdi_openness Y_t - delta_K K_t
    H_t+1   = H_t + g_H sqrt(education_spend health_spend) - delta_H H_t
    I_t+1   = I_t + phi_I connectivity_investment (Y_t/Y0) I_t (1 - I_t/I_max) - delta_I I_t
    S_t     = S_post + r_t (1 - S_post)          r_t from the scenario's stability path

A0 is solved so Y at the first year equals observed GDP per capita. The COVID
term starts in the first COVID year t_c and persists at rate rho
(``covid_persistence``); see its config entry for why rho = 1. The
connectivity equation is a diffusion form - adoption spreads from existing users
toward saturation - because Myanmar's internet use followed an S-curve; it also
keeps projections below 100%.

**The feedback loop.** Connectivity raises TFP, which raises Y, which raises
investment and so K, and speeds connectivity diffusion, which raises I again.
Stability multiplies TFP, so higher S shifts the whole loop up.

**From model to index.** Each modeled quantity maps to the development index's
indicators through :data:`~amber.config.SD_INDICATOR_LINKS`; the mapped values
then go through :func:`amber.modeling.index.compute_index` on the goalposts, so
futures sit on exactly the ruler history and the counterfactual use. Indicators
with no structural driver are excluded from the modeled index rather than held,
so they cannot manufacture index movement - and every modeled year uses the same
indicator set.

**Calibration** fits the calibrated parameters by bounded least squares so the
mapped indicators track Myanmar's actuals over 2011-2024, with residuals on the
goalpost scale (index units). The backtest is in-sample - the coup's effect
cannot be identified without post-2021 data. If its error exceeds
:data:`~amber.config.SD_CREDIBLE_NRMSE`, the result is marked not credible and
every chart calls the scenarios illustrative dynamics.

**Uncertainty.** Each scenario runs as an ensemble with calibrated parameters
jittered around the fit (the same draws for every scenario, so differences
between scenarios are not noise). The p10-p90 band is a sensitivity range, not a
confidence interval: it ignores parameter correlation and model-structure error.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from amber import config
from amber.config import LinkKind, Scenario
from amber.modeling import index as dev_index

logger = logging.getLogger(__name__)

__all__ = [
    "Backtest",
    "Calibration",
    "FutureRun",
    "InitialState",
    "SCConsistency",
    "Scenario",
    "SimulationResult",
    "backtest",
    "calibrate",
    "divergence_year",
    "historical_scenario",
    "initial_state",
    "modeled_indicators",
    "run",
    "run_scenarios",
    "sc_consistency",
    "simulate",
]

STOCKS: tuple[str, ...] = ("K", "H", "I", "S", "Y")
"""Stock and output series names, as in the equations."""

CALIBRATED: tuple[str, ...] = tuple(n for n, p in config.SD_PARAMETERS.items() if p.calibrate)

_ANCHORED_KINDS = frozenset(
    {
        LinkKind.OUTPUT,
        LinkKind.GROWTH,
        LinkKind.CONNECTIVITY,
        LinkKind.HUMAN_CAPITAL,
        LinkKind.ELASTICITY,
        LinkKind.BOUNDED,
    }
)
"""Kinds whose first-year value is imposed as an initial condition, so the
first year is excluded from calibration and error - it would be a free zero."""

_FLOOR = 1e-9
"""Stocks never fall to or below zero, so the power terms stay defined."""


def modeled_indicators() -> tuple[str, ...]:
    """Indicators the model produces, in config order."""
    return tuple(
        i for i, link in config.SD_INDICATOR_LINKS.items() if link.kind is not LinkKind.EXCLUDED
    )


def historical_scenario() -> Scenario:
    """What actually happened, as a scenario: the one calibration runs on."""
    return Scenario("historical", "History", config.SD_HISTORICAL_STABILITY)


def divergence_year(scenario: Scenario, end: int = config.SD_HORIZON_END) -> int | None:
    """First year a scenario differs from history - in stability or any lever.

    Args:
        scenario: The scenario to compare.
        end: Last year considered.

    Returns:
        The year, or ``None`` if the scenario never leaves the historical path.
    """
    years = np.arange(config.SD_BACKTEST_START, end + 1)
    history = historical_scenario()
    xs, rs = zip(*scenario.stability, strict=True)
    hx, hr = zip(*history.stability, strict=True)
    differs = ~np.isclose(np.interp(years, xs, rs), np.interp(years, hx, hr))
    levers_on = years >= config.SD_PROJECTION_START
    for name, lever in config.LEVERS.items():
        if not math.isclose(scenario.lever(name), lever.default):
            differs |= levers_on
    return int(years[differs][0]) if differs.any() else None


# --------------------------------------------------------------------------- #
# Initial state
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class InitialState:
    """Observed values the simulation starts from.

    Attributes:
        year: First simulated year.
        output: GDP per capita (sets Y0 and, through A0, the model's scale).
        connectivity: Internet users, % (I0).
        anchors: First-year value of each indicator whose link is anchored to it
            (life expectancy, and the elasticity-linked indicators).
        growth: Observed GDP growth in the first year, used as that year's
            modeled growth - it needs the year before, which is not simulated.
    """

    year: int
    output: float
    connectivity: float
    anchors: dict[str, float]
    growth: float


def initial_state(
    panel: pd.DataFrame,
    *,
    country: str = config.TREATED_COUNTRY,
    year: int = config.SD_BACKTEST_START,
) -> InitialState:
    """Read the starting values from the panel.

    Args:
        panel: Tidy panel, normally ``panel_interpolated``.
        country: ISO3 of the modeled country.
        year: First simulated year.

    Returns:
        The initial state.

    Raises:
        ValueError: If any value the start needs is missing.
    """
    rows = panel[(panel[config.COL_COUNTRY_ISO3] == country) & (panel[config.COL_YEAR] == year)]
    values = rows.set_index(config.COL_INDICATOR_ID)[config.COL_VALUE]

    needed = {config.SD_OUTPUT_INDICATOR, config.SD_CONNECTIVITY_INDICATOR}
    anchored = {
        i
        for i, link in config.SD_INDICATOR_LINKS.items()
        if link.kind in {LinkKind.HUMAN_CAPITAL, LinkKind.ELASTICITY, LinkKind.BOUNDED}
    }
    growth_ids = {
        i for i, link in config.SD_INDICATOR_LINKS.items() if link.kind is LinkKind.GROWTH
    }
    required = needed | anchored | growth_ids
    missing = sorted(i for i in required if pd.isna(values.get(i)))
    if missing:
        msg = f"{country} {year}: missing starting values for {missing}"
        raise ValueError(msg)

    return InitialState(
        year=year,
        output=float(values[config.SD_OUTPUT_INDICATOR]),
        connectivity=float(values[config.SD_CONNECTIVITY_INDICATOR]),
        anchors={i: float(values[i]) for i in sorted(anchored)},
        growth=float(values[next(iter(growth_ids))]) if growth_ids else float("nan"),
    )


# --------------------------------------------------------------------------- #
# The step function
# --------------------------------------------------------------------------- #

ParamArrays = dict[str, np.ndarray]
"""Parameter name -> values, one per ensemble member (shape ``(M,)``)."""


def _as_arrays(params: Mapping[str, float] | ParamArrays) -> ParamArrays:
    """Fill in fixed/default parameters and broadcast everything to ``(M,)``."""
    merged = {name: p.value for name, p in config.SD_PARAMETERS.items()}
    merged.update(params)
    arrays = {name: np.atleast_1d(np.asarray(v, dtype=float)) for name, v in merged.items()}
    size = max(a.size for a in arrays.values())
    return {name: np.broadcast_to(a, (size,)).copy() for name, a in arrays.items()}


def _stability(scenario: Scenario, years: np.ndarray, stability_post: np.ndarray) -> np.ndarray:
    """S by member and year, from the scenario's recovery path."""
    xs, rs = zip(*scenario.stability, strict=True)
    recovery = np.interp(years, xs, rs)  # holds the end values outside the breakpoints
    post = stability_post[:, None]
    return post + recovery[None, :] * (1.0 - post)


def _levers(scenario: Scenario, years: np.ndarray) -> dict[str, np.ndarray]:
    """Each lever by year: its default before the projection starts, the scenario's after."""
    active = years >= config.SD_PROJECTION_START
    return {
        name: np.where(active, scenario.lever(name), lever.default)
        for name, lever in config.LEVERS.items()
    }


def _covid_factor(params: ParamArrays, years: np.ndarray) -> np.ndarray:
    """Output multiplier for COVID: a loss from the first COVID year, decaying at rho."""
    first = min(config.COVID_CONFOUNDED_YEARS)
    elapsed = np.maximum(years - first, 0)[None, :]
    loss = params["covid_shock"][:, None] * params["covid_persistence"][:, None] ** elapsed
    return np.where(years[None, :] >= first, 1.0 - loss, 1.0)


def _simulate_arrays(
    params: ParamArrays,
    scenario: Scenario,
    initial: InitialState,
    years: np.ndarray,
) -> dict[str, np.ndarray]:
    """Run the difference equations for every member at once.

    Returns:
        Stock/output name -> array of shape ``(M, T)``.
    """
    p = params
    n_members, n_years = p["alpha"].size, years.size
    i_max = config.GOALPOSTS[config.SD_CONNECTIVITY_INDICATOR].high
    lever = _levers(scenario, years)
    s = _stability(scenario, years, p["stability_post"])
    covid = _covid_factor(p, years)

    k = np.empty((n_members, n_years))
    h = np.empty_like(k)
    i = np.empty_like(k)
    y = np.empty_like(k)
    k[:, 0] = p["capital_output_ratio"] * initial.output
    h[:, 0] = 1.0
    i[:, 0] = initial.connectivity

    # Solve A0 so the first year reproduces observed output exactly.
    base = (
        covid[:, 0]
        * s[:, 0] ** p["stability_elasticity"]
        * (1.0 + p["connectivity_tfp"] * i[:, 0] / i_max)
        * k[:, 0] ** p["alpha"]
        * h[:, 0] ** p["beta"]
    )
    a0 = initial.output / base

    for t in range(n_years):
        tfp = (
            a0
            * (1.0 + p["tfp_growth"]) ** (years[t] - years[0])
            * covid[:, t]
            * s[:, t] ** p["stability_elasticity"]
            * (1.0 + p["connectivity_tfp"] * i[:, t] / i_max)
        )
        y[:, t] = tfp * k[:, t] ** p["alpha"] * h[:, t] ** p["beta"]
        if t == n_years - 1:
            break

        invest = p["savings_rate"] * lever["fdi_openness"][t] * y[:, t]
        k[:, t + 1] = np.maximum(k[:, t] + invest - p["delta_k"] * k[:, t], _FLOOR)

        spend = math.sqrt(lever["education_spend"][t] * lever["health_spend"][t])
        gain_h = p["human_capital_gain"] * spend
        h[:, t + 1] = np.maximum(h[:, t] + gain_h - p["delta_h"] * h[:, t], _FLOOR)

        diffusion = (
            p["connectivity_gain"]
            * lever["connectivity_investment"][t]
            * (y[:, t] / initial.output)
            * i[:, t]
            * (1.0 - i[:, t] / i_max)
        )
        i_next = i[:, t] + diffusion - p["delta_i"] * i[:, t]
        i[:, t + 1] = np.clip(i_next, _FLOOR, i_max)

    return {"K": k, "H": h, "I": i, "S": s, "Y": y}


def _map_indicators(
    state: Mapping[str, np.ndarray],
    params: ParamArrays,
    scenario: Scenario,
    initial: InitialState,
    years: np.ndarray,
) -> dict[str, np.ndarray]:
    """Turn model quantities into indicator values via the configured links."""
    lever = _levers(scenario, years)
    y, h, i, s = state["Y"], state["H"], state["I"], state["S"]
    out: dict[str, np.ndarray] = {}

    for indicator_id, link in config.SD_INDICATOR_LINKS.items():
        args = [params[name][:, None] for name in link.params]
        match link.kind:
            case LinkKind.OUTPUT:
                out[indicator_id] = y
            case LinkKind.GROWTH:
                growth = np.empty_like(y)
                growth[:, 0] = initial.growth
                growth[:, 1:] = 100.0 * (y[:, 1:] / y[:, :-1] - 1.0) + args[0]
                out[indicator_id] = growth
            case LinkKind.CONNECTIVITY:
                out[indicator_id] = i
            case LinkKind.HUMAN_CAPITAL:
                out[indicator_id] = initial.anchors[indicator_id] * h
            case LinkKind.ELASTICITY:
                out[indicator_id] = initial.anchors[indicator_id] * h ** args[0]
            case LinkKind.BOUNDED:
                ceiling = config.GOALPOSTS[indicator_id].high
                gap = ceiling - initial.anchors[indicator_id]
                out[indicator_id] = ceiling - gap * h ** (-args[0])
            case LinkKind.SATURATING:
                out[indicator_id] = args[0] * (1.0 - np.exp(-i / args[1])) * s
            case LinkKind.STABILITY_SHARE:
                out[indicator_id] = args[0] * lever[str(link.lever)][None, :] * s
            case LinkKind.LEVER_SHARE:
                out[indicator_id] = np.broadcast_to(
                    args[0] * lever[str(link.lever)][None, :], y.shape
                ).copy()
            case LinkKind.EXCLUDED:
                continue
    return out


def _to_panel(indicators: Mapping[str, np.ndarray], years: np.ndarray) -> pd.DataFrame:
    """Indicator arrays as a tidy panel, one pseudo-country per member."""
    n_members = next(iter(indicators.values())).shape[0]
    members = [f"m{m:04d}" for m in range(n_members)]
    name = config.COUNTRIES[config.TREATED_COUNTRY]
    frames = [
        pd.DataFrame(
            {
                config.COL_INDICATOR_ID: indicator_id,
                config.COL_COUNTRY_ISO3: np.repeat(members, years.size),
                config.COL_COUNTRY_NAME: name,
                config.COL_YEAR: np.tile(years, n_members),
                config.COL_VALUE: values.ravel(),
                config.COL_PRE_2011: np.tile(years < config.MODELING_WINDOW_START, n_members),
            }
        )
        for indicator_id, values in indicators.items()
    ]
    return pd.concat(frames, ignore_index=True)


def _index_series(indicators: Mapping[str, np.ndarray], years: np.ndarray) -> dict[str, np.ndarray]:
    """Pillars and combined index for every member, as ``(M, T)`` arrays."""
    scored = dev_index.compute_index(_to_panel(indicators, years), method="goalposts")
    n_members = next(iter(indicators.values())).shape[0]
    out = {}
    for series in config.INDEX_SERIES:
        wide = scored[scored[config.COL_SERIES] == series].pivot(
            index=config.COL_COUNTRY_ISO3, columns=config.COL_YEAR, values=config.COL_VALUE
        )
        wide = wide.reindex(index=[f"m{m:04d}" for m in range(n_members)], columns=years)
        out[series] = wide.to_numpy()
    return out


def simulate(
    scenario: Scenario,
    params: Mapping[str, float],
    initial: InitialState,
    *,
    start: int | None = None,
    end: int = config.SD_HORIZON_END,
) -> pd.DataFrame:
    """Simulate one scenario with one parameter set.

    Args:
        scenario: The scenario to run.
        params: Parameter values; unset ones take their config value.
        initial: Starting values.
        start: First year (defaults to the initial state's year).
        end: Last year.

    Returns:
        Years x series: the stocks (K, H, I, S, Y), every modeled indicator, the
        pillars and the combined index.
    """
    years = np.arange(start or initial.year, end + 1)
    arrays = _as_arrays(params)
    state = _simulate_arrays(arrays, scenario, initial, years)
    indicators = _map_indicators(state, arrays, scenario, initial, years)
    index = _index_series(indicators, years)
    columns = {**state, **indicators, **index}
    return pd.DataFrame({name: values[0] for name, values in columns.items()}, index=years)


# --------------------------------------------------------------------------- #
# Calibration and backtest
# --------------------------------------------------------------------------- #


def _score(values: np.ndarray | pd.Series, indicator_id: str) -> np.ndarray:
    """Place values on the goalpost scale, unclipped: the index's own units."""
    goalpost = config.GOALPOSTS[indicator_id]
    low, high = goalpost.low, goalpost.high
    values = np.asarray(values, dtype=float)
    if indicator_id in config.LOG_TRANSFORM:
        with np.errstate(divide="ignore", invalid="ignore"):
            return (np.log(values) - math.log(low)) / (math.log(high) - math.log(low))
    return (values - low) / (high - low)


def _actuals(panel: pd.DataFrame, years: np.ndarray, country: str) -> pd.DataFrame:
    """Years x modeled indicators of observed values for the modeled country."""
    rows = panel[
        (panel[config.COL_COUNTRY_ISO3] == country)
        & panel[config.COL_INDICATOR_ID].isin(modeled_indicators())
    ]
    wide = rows.pivot_table(
        index=config.COL_YEAR, columns=config.COL_INDICATOR_ID, values=config.COL_VALUE
    )
    return wide.reindex(index=years, columns=list(modeled_indicators()))


def _residual_mask(actual: pd.DataFrame, first_year: int) -> pd.DataFrame:
    """Which observations count: observed, and not imposed as an initial condition."""
    mask = actual.notna()
    for indicator_id in actual.columns:
        if config.SD_INDICATOR_LINKS[indicator_id].kind in _ANCHORED_KINDS:
            mask.loc[first_year, indicator_id] = False
    return mask


@dataclass(frozen=True, slots=True)
class Calibration:
    """Fitted parameters and what they were fitted to.

    Attributes:
        params: Every parameter - fixed at its config value or fitted.
        initial: The starting values the fit used.
        cost: Half the sum of squared residuals at the optimum.
        n_residuals: Observations fitted.
    """

    params: dict[str, float]
    initial: InitialState
    cost: float
    n_residuals: int

    @property
    def fitted(self) -> dict[str, float]:
        """Only the calibrated parameters."""
        return {name: self.params[name] for name in CALIBRATED}


def _residual_function(
    actual: pd.DataFrame,
    mask: pd.DataFrame,
    initial: InitialState,
    years: np.ndarray,
    scenario: Scenario,
) -> Callable[[np.ndarray], np.ndarray]:
    """Build the residual vector scipy minimizes: model minus actual, goalpost scale."""
    targets = {i: _score(actual[i].to_numpy(), i) for i in actual.columns}
    keep = {i: mask[i].to_numpy() for i in actual.columns}

    def residuals(x: np.ndarray) -> np.ndarray:
        arrays = _as_arrays(dict(zip(CALIBRATED, x, strict=True)))
        state = _simulate_arrays(arrays, scenario, initial, years)
        mapped = _map_indicators(state, arrays, scenario, initial, years)
        parts = [(_score(mapped[i][0], i) - targets[i])[keep[i]] for i in actual.columns]
        out = np.concatenate(parts)
        return np.nan_to_num(out, nan=10.0, posinf=10.0, neginf=-10.0)

    return residuals


def calibrate(
    panel: pd.DataFrame,
    *,
    country: str = config.TREATED_COUNTRY,
    start: int = config.SD_BACKTEST_START,
    end: int = config.SD_BACKTEST_END,
    restarts: int = config.SD_CALIBRATION_RESTARTS,
    seed: int = config.SD_SEED,
) -> Calibration:
    """Fit the calibrated parameters to the modeled country's history.

    Bounded least squares (trust-region reflective) from the config defaults and
    ``restarts - 1`` seeded draws inside the bounds; the lowest cost wins.

    Args:
        panel: Tidy panel, normally ``panel_interpolated``.
        country: ISO3 of the modeled country.
        start: First calibration year (the initial state's year).
        end: Last calibration year.
        restarts: Least-squares starts.
        seed: RNG seed for the restart draws.

    Returns:
        The fitted calibration.
    """
    years = np.arange(start, end + 1)
    initial = initial_state(panel, country=country, year=start)
    actual = _actuals(panel, years, country)
    mask = _residual_mask(actual, start)
    residuals = _residual_function(actual, mask, initial, years, historical_scenario())

    specs = [config.SD_PARAMETERS[name] for name in CALIBRATED]
    low = np.array([p.low for p in specs])
    high = np.array([p.high for p in specs])
    rng = np.random.default_rng(seed)
    starts = [np.array([p.value for p in specs])]
    starts += [rng.uniform(low, high) for _ in range(restarts - 1)]

    best = None
    for x0 in starts:
        fit = least_squares(residuals, x0, bounds=(low, high), method="trf", max_nfev=4000)
        if best is None or fit.cost < best.cost:
            best = fit
    assert best is not None  # at least one start

    params = {name: p.value for name, p in config.SD_PARAMETERS.items()}
    params.update(dict(zip(CALIBRATED, best.x.tolist(), strict=True)))
    logger.info(
        "Calibrated %d parameters on %d observations (%d-%d): cost %.4g",
        len(CALIBRATED),
        int(mask.to_numpy().sum()),
        start,
        end,
        best.cost,
    )
    return Calibration(
        params=params, initial=initial, cost=float(best.cost), n_residuals=int(mask.sum().sum())
    )


@dataclass(frozen=True, slots=True)
class Backtest:
    """How well the calibrated model reproduces history.

    Attributes:
        modeled: Years x indicators, the calibrated model's values.
        actual: Years x indicators, observed values.
        nrmse: Per-indicator RMSE on the goalpost scale (index units).
        n_obs: Observations behind each nRMSE.
        overall: RMSE over every fitted observation, pooled.
        credible: Whether ``overall`` is within the credibility threshold.
        combined_modeled: The modeled combined index by year.
        combined_actual: The actual combined index recomputed on the modeled
            indicators only, so the comparison is like for like.
    """

    modeled: pd.DataFrame
    actual: pd.DataFrame
    nrmse: pd.Series
    n_obs: pd.Series
    overall: float
    credible: bool
    combined_modeled: pd.Series
    combined_actual: pd.Series

    @property
    def combined_nrmse(self) -> float:
        """RMSE of the modeled combined index against the like-for-like actual."""
        gap = (self.combined_modeled - self.combined_actual).dropna()
        return float(np.sqrt(np.mean(np.square(gap)))) if len(gap) else float("nan")


def backtest(
    calibration: Calibration,
    panel: pd.DataFrame,
    *,
    country: str = config.TREATED_COUNTRY,
    end: int = config.SD_BACKTEST_END,
    threshold: float | None = None,
) -> Backtest:
    """Replay history with the calibrated parameters and measure the error.

    Args:
        calibration: Output of :func:`calibrate`.
        panel: Tidy panel the calibration used.
        country: ISO3 of the modeled country.
        end: Last backtest year.
        threshold: Credibility threshold; defaults to
            :data:`~amber.config.SD_CREDIBLE_NRMSE`.

    Returns:
        Per-indicator and overall error, and the credibility verdict.
    """
    threshold = config.SD_CREDIBLE_NRMSE if threshold is None else threshold
    start = calibration.initial.year
    years = np.arange(start, end + 1)
    frame = simulate(historical_scenario(), calibration.params, calibration.initial, end=end)
    actual = _actuals(panel, years, country)
    mask = _residual_mask(actual, start)

    residuals = {
        i: (_score(frame[i].to_numpy(), i) - _score(actual[i].to_numpy(), i))[mask[i].to_numpy()]
        for i in actual.columns
    }
    nrmse = pd.Series(
        {
            i: float(np.sqrt(np.mean(np.square(r)))) if r.size else float("nan")
            for i, r in residuals.items()
        },
        name="nrmse",
    )
    n_obs = pd.Series({i: int(r.size) for i, r in residuals.items()}, name="n_obs")
    pooled = np.concatenate(list(residuals.values()))
    overall = float(np.sqrt(np.mean(np.square(pooled))))

    matched = panel[
        (panel[config.COL_COUNTRY_ISO3] == country)
        & panel[config.COL_INDICATOR_ID].isin(modeled_indicators())
    ]
    actual_index = dev_index.compute_index(matched, method="goalposts")
    combined_actual = (
        actual_index[actual_index[config.COL_SERIES] == config.COMBINED_SERIES]
        .set_index(config.COL_YEAR)[config.COL_VALUE]
        .reindex(years)
    )

    credible = overall <= threshold
    logger.info(
        "Backtest %d-%d: overall nRMSE %.3f (%s at %.2f); combined-index RMSE %.3f",
        start,
        end,
        overall,
        "credible" if credible else "NOT credible",
        threshold,
        float(np.sqrt(np.nanmean(np.square(frame[config.COMBINED_SERIES] - combined_actual)))),
    )
    return Backtest(
        modeled=frame[list(actual.columns)],
        actual=actual,
        nrmse=nrmse,
        n_obs=n_obs,
        overall=overall,
        credible=credible,
        combined_modeled=frame[config.COMBINED_SERIES].rename("modeled"),
        combined_actual=combined_actual.rename("actual"),
    )


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """One scenario, run as an ensemble.

    Attributes:
        scenario: The scenario.
        years: Simulated years.
        central: Years x series for the unjittered calibration (member 0).
        bands: Tidy ``[year, series, quantile, value]`` across the ensemble.
    """

    scenario: Scenario
    years: tuple[int, ...]
    central: pd.DataFrame
    bands: pd.DataFrame

    def band(self, series: str, quantile: str) -> pd.Series:
        """One quantile of one series, by year."""
        rows = self.bands[
            (self.bands[config.COL_SERIES] == series)
            & (self.bands[config.COL_QUANTILE] == quantile)
        ]
        return rows.set_index(config.COL_YEAR)[config.COL_VALUE].rename(f"{series} {quantile}")


def _ensemble(
    calibration: Calibration,
    size: int,
    jitter: float,
    seed: int,
) -> ParamArrays:
    """Member 0 is the calibration; the rest jitter every calibrated parameter."""
    rng = np.random.default_rng(seed)
    arrays: ParamArrays = {}
    for name, spec in config.SD_PARAMETERS.items():
        value = calibration.params[name]
        members = np.full(size, value)
        if spec.calibrate and size > 1:
            draws = rng.uniform(1.0 - jitter, 1.0 + jitter, size - 1)
            members[1:] = np.clip(value * draws, spec.low, spec.high)
        arrays[name] = members
    return arrays


def run_scenarios(
    calibration: Calibration,
    scenarios: Sequence[Scenario] = config.SCENARIOS,
    *,
    size: int = config.SD_ENSEMBLE_SIZE,
    jitter: float = config.SD_PARAM_JITTER,
    seed: int = config.SD_SEED,
    end: int = config.SD_HORIZON_END,
) -> dict[str, SimulationResult]:
    """Run every scenario as an ensemble on common parameter draws.

    Args:
        calibration: Output of :func:`calibrate`.
        scenarios: Scenarios to run.
        size: Ensemble members (member 0 is the unjittered calibration).
        jitter: Uniform multiplicative spread on each calibrated parameter.
        seed: RNG seed for the draws.
        end: Last simulated year.

    Returns:
        Scenario name -> result.
    """
    initial = calibration.initial
    years = np.arange(initial.year, end + 1)
    params = _ensemble(calibration, size, jitter, seed)
    quantiles = config.SD_QUANTILES

    results: dict[str, SimulationResult] = {}
    for scenario in scenarios:
        state = _simulate_arrays(params, scenario, initial, years)
        indicators = _map_indicators(state, params, scenario, initial, years)
        series = {**state, **indicators, **_index_series(indicators, years)}

        central = pd.DataFrame({name: values[0] for name, values in series.items()}, index=years)
        rows = []
        for name, values in series.items():
            for label, q in quantiles.items():
                rows.append(
                    pd.DataFrame(
                        {
                            config.COL_YEAR: years,
                            config.COL_SERIES: name,
                            config.COL_QUANTILE: label,
                            config.COL_VALUE: np.nanquantile(values, q, axis=0),
                        }
                    )
                )
        results[scenario.name] = SimulationResult(
            scenario=scenario,
            years=tuple(int(y) for y in years),
            central=central,
            bands=pd.concat(rows, ignore_index=True),
        )
        logger.info(
            "%s: combined index %d = %.3f (p10-p90 %.3f-%.3f)",
            scenario.name,
            end,
            central[config.COMBINED_SERIES].iloc[-1],
            results[scenario.name].band(config.COMBINED_SERIES, "p10").iloc[-1],
            results[scenario.name].band(config.COMBINED_SERIES, "p90").iloc[-1],
        )
    return results


# --------------------------------------------------------------------------- #
# Consistency with the counterfactual
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SCConsistency:
    """How far the no-coup scenario sits from the phase 3 synthetic control.

    Attributes:
        outcome: The SC outcome compared.
        years: Overlap years compared.
        deviation: Largest ``|scenario p50 - synthetic| / synthetic`` over the
            overlap; NaN where the SC itself is not credible.
        sc_credible: The phase 3 credibility verdict for this outcome.
        consistent: ``deviation <= tolerance``; ``None`` if not applicable.
    """

    outcome: str
    years: tuple[int, ...]
    deviation: float
    sc_credible: bool
    consistent: bool | None


def sc_consistency(
    result: SimulationResult,
    sc_paths: pd.DataFrame,
    sc_metrics: pd.DataFrame,
    *,
    tolerance: float = config.SD_SC_TOLERANCE,
) -> tuple[SCConsistency, ...]:
    """Compare a scenario with the synthetic control over their overlap.

    Only a credible synthetic control is a reference; for one that is not, the
    deviation is reported as NaN rather than measured against a bad fit.

    Args:
        result: The scenario to check - normally no-coup.
        sc_paths: Tidy ``synthetic_control`` table from phase 3.
        sc_metrics: ``sc_metrics`` table from phase 3.
        tolerance: Largest relative deviation counted as consistent.

    Returns:
        One check per SC outcome the scenario also produces.
    """
    checks = []
    credible = sc_metrics.set_index(config.COL_OUTCOME)["credible"].astype(bool).to_dict()
    for outcome in sorted(set(sc_paths[config.COL_OUTCOME])):
        if outcome not in result.central.columns:
            continue
        synthetic = (
            sc_paths[
                (sc_paths[config.COL_OUTCOME] == outcome)
                & (sc_paths[config.COL_SERIES] == "synthetic")
                & (sc_paths[config.COL_YEAR] >= config.TREATMENT_YEAR)
            ]
            .set_index(config.COL_YEAR)[config.COL_VALUE]
            .dropna()
        )
        scenario = result.band(outcome, "p50").reindex(synthetic.index)
        years = tuple(int(y) for y in synthetic.index[scenario.notna()])
        is_credible = bool(credible.get(outcome, False))
        if not is_credible or not years:
            deviation, consistent = float("nan"), None
        else:
            rel = ((scenario - synthetic).abs() / synthetic.abs()).dropna()
            deviation = float(rel.max())
            consistent = deviation <= tolerance
        checks.append(
            SCConsistency(
                outcome=outcome,
                years=years,
                deviation=deviation,
                sc_credible=is_credible,
                consistent=consistent,
            )
        )
        logger.info(
            "SC consistency for %s: deviation %s (%s)",
            outcome,
            "n/a" if math.isnan(deviation) else f"{deviation:.1%}",
            "SC not credible" if not is_credible else ("ok" if consistent else "RED FLAG"),
        )
    return tuple(checks)


# --------------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FutureRun:
    """Everything the future layer produces.

    Attributes:
        calibration: The fitted parameters.
        backtest: Fit to history and the credibility verdict.
        results: Scenario name -> ensemble result.
        sc_checks: Consistency of the no-coup scenario with phase 3.
    """

    calibration: Calibration
    backtest: Backtest
    results: dict[str, SimulationResult]
    sc_checks: tuple[SCConsistency, ...] = field(default_factory=tuple)

    @property
    def credible(self) -> bool:
        """Whether the scenarios count as a calibrated projection."""
        return self.backtest.credible


def run(
    panel: pd.DataFrame,
    *,
    sc_paths: pd.DataFrame | None = None,
    sc_metrics: pd.DataFrame | None = None,
    scenarios: Sequence[Scenario] = config.SCENARIOS,
    size: int = config.SD_ENSEMBLE_SIZE,
    jitter: float = config.SD_PARAM_JITTER,
    seed: int = config.SD_SEED,
    restarts: int = config.SD_CALIBRATION_RESTARTS,
    end: int = config.SD_HORIZON_END,
) -> FutureRun:
    """Calibrate, backtest, run every scenario and check against phase 3.

    Args:
        panel: Tidy panel, normally ``panel_interpolated``.
        sc_paths: Phase 3 ``synthetic_control`` table, for the consistency check.
        sc_metrics: Phase 3 ``sc_metrics`` table, for its credibility verdicts.
        scenarios: Scenarios to run.
        size: Ensemble members per scenario.
        jitter: Ensemble parameter spread.
        seed: RNG seed for calibration restarts and the ensemble.
        restarts: Least-squares starts.
        end: Last simulated year.

    Returns:
        Calibration, backtest, scenario results and consistency checks.
    """
    calibration = calibrate(panel, restarts=restarts, seed=seed)
    bt = backtest(calibration, panel)
    results = run_scenarios(calibration, scenarios, size=size, jitter=jitter, seed=seed, end=end)

    checks: tuple[SCConsistency, ...] = ()
    counterfactual = results.get(config.SD_COUNTERFACTUAL_SCENARIO)
    if sc_paths is not None and sc_metrics is not None and counterfactual is not None:
        checks = sc_consistency(counterfactual, sc_paths, sc_metrics)
    elif counterfactual is not None:
        logger.warning("Phase 3 outputs not supplied; skipping the SC consistency check")
    return FutureRun(calibration=calibration, backtest=bt, results=results, sc_checks=checks)

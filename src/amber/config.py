"""Central configuration for the Amber data layer.

Every constant that encodes a *modeling decision* lives here rather than in the
logic modules, so that the assumptions behind the analysis are inspectable in one
place. The rationale for these choices is documented in
``docs/myanmar-precoup-calibration-reference.md``.

Key decisions encoded below:

* **World Bank WDI is the single source of truth** for every numeric series.
  IMF figures quoted in the calibration reference are a cross-check only - they
  use a fiscal-year basis and must never be mixed into the panel.
* **The treatment year is 2021** (the February coup).
* **Data is fetched from 2000**, but the modeling window is anchored at 2011;
  pre-2011 figures are military-era and unreliable, so rows carry a ``pre_2011``
  flag and are excluded from calibration downstream.
* **The donor pool** excludes countries with their own concurrent 2021+ shock
  (notably Sri Lanka, whose 2022 crisis would contaminate the counterfactual).
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv()


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

DATA_DIR: Final[Path] = Path(os.getenv("AMBER_DATA_DIR", PROJECT_ROOT / "data"))
"""Root of the data tree. Override with ``AMBER_DATA_DIR`` for a scratch run."""

RAW_DATA_DIR: Final[Path] = DATA_DIR / "raw"
"""Unmodified API responses, cached so the pipeline is re-runnable offline."""

PROCESSED_DATA_DIR: Final[Path] = DATA_DIR / "processed"
"""Generated outputs. Disposable - always reproducible from ``raw``."""

RELEASE_DATA_DIR: Final[Path] = DATA_DIR / "release"
"""A committed snapshot of the processed tables the API serves in production.
Regenerated deliberately with ``make release``, never edited by hand."""

LOG_LEVEL: Final[str] = os.getenv("AMBER_LOG_LEVEL", "INFO").upper()


# --------------------------------------------------------------------------- #
# Modeling window
# --------------------------------------------------------------------------- #

YEAR_START: Final[int] = 2000
"""First year fetched. Earlier years exist but are not useful here."""

YEAR_END: Final[int] = 2024
"""Last year fetched. Recent years are sparse until sources publish."""

MODELING_WINDOW_START: Final[int] = 2011
"""Start of the reform era and of the calibration window.

Pre-2011 statistics come from the military era and are not considered reliable
enough to fit a synthetic control against.
"""

TREATMENT_YEAR: Final[int] = 2021
"""The February 2021 coup - the synthetic-control treatment point.

Stored as a constant rather than a per-row column: it is a property of the
analysis, not of any observation.
"""

COVID_CONFOUNDED_YEARS: Final[tuple[int, ...]] = (2020,)
"""Years whose shock is COVID, not the coup.

The clean pre-treatment window is therefore ~2011-2019. See the calibration
reference, section 1, caveat 1.
"""


# --------------------------------------------------------------------------- #
# Countries
# --------------------------------------------------------------------------- #

TREATED_COUNTRY: Final[str] = "MMR"
"""The unit under study. Everything else below is the donor pool."""

DONOR_POOL: Final[dict[str, str]] = {
    "VNM": "Vietnam",
    "KHM": "Cambodia",
    "BGD": "Bangladesh",
    "LAO": "Lao PDR",
    "NPL": "Nepal",
    "IDN": "Indonesia",
}
"""Regional peers that did not rupture in 2021, as ISO3 -> display name.

Sri Lanka is deliberately absent: its 2022 economic crisis is a concurrent shock
that would contaminate the synthetic control.
"""

COUNTRIES: Final[dict[str, str]] = {TREATED_COUNTRY: "Myanmar", **DONOR_POOL}
"""Every country fetched, as ISO3 -> display name."""

COUNTRY_CODES: Final[tuple[str, ...]] = tuple(COUNTRIES)


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #


class Pillar(StrEnum):
    """The three dimensions of the combined development index.

    Aggregated geometric-mean style downstream, so that weakness in one pillar
    cannot be masked by strength in another.
    """

    ECONOMY = "economy"
    INNOVATION = "innovation"
    HUMAN_DEVELOPMENT = "human_development"


@dataclass(frozen=True, slots=True)
class Indicator:
    """One World Bank series and the pillar it belongs to.

    Attributes:
        id: World Bank WDI series code, e.g. ``NY.GDP.PCAP.KD``.
        name: Human-readable label carried through to the panel.
        pillar: Which index pillar this series feeds.
    """

    id: str
    name: str
    pillar: Pillar


INDICATORS: Final[tuple[Indicator, ...]] = (
    # --- Economy ----------------------------------------------------------- #
    Indicator("NY.GDP.PCAP.KD", "GDP per capita (constant 2015 US$)", Pillar.ECONOMY),
    Indicator("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)", Pillar.ECONOMY),
    Indicator("BX.KLT.DINV.WD.GD.ZS", "FDI net inflows (% of GDP)", Pillar.ECONOMY),
    Indicator(
        "SI.POV.DDAY",
        "Poverty headcount ratio at $2.15/day (% of population)",
        Pillar.ECONOMY,
    ),
    # --- Innovation / technology ------------------------------------------- #
    Indicator("IT.NET.USER.ZS", "Internet users (% of population)", Pillar.INNOVATION),
    Indicator("IT.CEL.SETS.P2", "Mobile subscriptions (per 100 people)", Pillar.INNOVATION),
    Indicator(
        "TX.VAL.TECH.MF.ZS",
        "High-tech exports (% of manufactured exports)",
        Pillar.INNOVATION,
    ),
    # --- Human development -------------------------------------------------- #
    Indicator("SP.DYN.LE00.IN", "Life expectancy at birth (years)", Pillar.HUMAN_DEVELOPMENT),
    Indicator(
        "SH.DYN.MORT",
        "Under-5 mortality (per 1,000 live births)",
        Pillar.HUMAN_DEVELOPMENT,
    ),
    Indicator("SE.SEC.ENRR", "Secondary school enrollment (% gross)", Pillar.HUMAN_DEVELOPMENT),
    Indicator(
        "SH.XPD.CHEX.GD.ZS",
        "Current health expenditure (% of GDP)",
        Pillar.HUMAN_DEVELOPMENT,
    ),
)

INDICATORS_BY_ID: Final[dict[str, Indicator]] = {ind.id: ind for ind in INDICATORS}

PILLAR_BY_INDICATOR: Final[dict[str, Pillar]] = {ind.id: ind.pillar for ind in INDICATORS}


# --------------------------------------------------------------------------- #
# Development index
# --------------------------------------------------------------------------- #


class Polarity(StrEnum):
    """Which direction of an indicator counts as development."""

    POSITIVE = "positive"
    """Higher is better, e.g. life expectancy."""

    NEGATIVE = "negative"
    """Lower is better, e.g. under-5 mortality. Inverted during normalization."""


INDICATOR_POLARITY: Final[dict[str, Polarity]] = {
    "NY.GDP.PCAP.KD": Polarity.POSITIVE,
    "NY.GDP.MKTP.KD.ZG": Polarity.POSITIVE,
    "BX.KLT.DINV.WD.GD.ZS": Polarity.POSITIVE,
    "SI.POV.DDAY": Polarity.NEGATIVE,
    "IT.NET.USER.ZS": Polarity.POSITIVE,
    "IT.CEL.SETS.P2": Polarity.POSITIVE,
    "TX.VAL.TECH.MF.ZS": Polarity.POSITIVE,
    "SP.DYN.LE00.IN": Polarity.POSITIVE,
    "SH.DYN.MORT": Polarity.NEGATIVE,
    "SE.SEC.ENRR": Polarity.POSITIVE,
    "SH.XPD.CHEX.GD.ZS": Polarity.POSITIVE,
}
"""Direction of every indicator.

Listed explicitly rather than defaulting to positive, so that adding an
indicator forces a decision about which way is up.
"""

INDEX_EXCLUDED: Final[dict[str, str]] = {
    "SI.POV.DDAY": "Three Myanmar observations (2015-2017), unreported since. In the index it "
    "entered Myanmar's score for those three years only - a composition effect, not "
    "development - and no counterfactual or projection can carry it",
    "TX.VAL.TECH.MF.ZS": "Erratic for Myanmar (0.2-7.5%) with no structural driver, so no "
    "counterfactual or projection can produce it; in the index it held the innovation "
    "pillar near its floor with noise rather than signal",
}
"""Indicators kept in the panel as descriptive history but left out of the index.

The index must mean the same thing in history, the counterfactual and the
projections, so it holds only indicators every layer can produce. Polarity and
goalposts stay configured for these, so an exclusion is reversible in one line.
"""

INDEX_INDICATORS: Final[tuple[str, ...]] = tuple(
    ind.id for ind in INDICATORS if ind.id not in INDEX_EXCLUDED
)
"""The indicators the development index is built from, in config order."""

LOG_TRANSFORM: Final[frozenset[str]] = frozenset({"NY.GDP.PCAP.KD"})
"""Indicators taken as ln(x) before normalization.

Income, following the HDI: an extra $1,000 matters far more at $1,000 per head
than at $5,000.
"""


class Normalization(StrEnum):
    """How indicator scores are scaled to [0, 1]."""

    GOALPOSTS = "goalposts"
    """Fixed per-indicator bounds from :data:`GOALPOSTS`. The default."""

    POOLED = "pooled"
    """Min-max over the panel itself. Kept for comparison only: scores then
    shift whenever a country or a data year is added, and values outside the
    historical range - counterfactuals, projections - are clipped."""


DEFAULT_NORMALIZATION: Final[Normalization] = Normalization.GOALPOSTS


@dataclass(frozen=True, slots=True)
class Goalpost:
    """Fixed normalization bounds for one indicator, in its raw units.

    ``low`` and ``high`` are the ends of the scale, not "worst" and "best" -
    :data:`INDICATOR_POLARITY` decides which end scores 1. For a log-transformed
    indicator both are logged at normalization time.

    Attributes:
        low: Lower bound of the scale.
        high: Upper bound of the scale.
        source: Where the bound comes from, precisely enough to re-derive it.
    """

    low: float
    high: float
    source: str


GOALPOST_PADDING: Final[float] = 0.25
"""Padding for seeded goalposts, as a share of the observed span on each side.

Span-based rather than value-based so it widens ranges that cross zero (growth,
FDI) instead of narrowing them.
"""

_SEEDED = (
    "Seeded 2026-09-30 from the pooled WDI range, 7 countries x 2011-2024 "
    "(interpolated panel), padded by 25% of span each side"
)

GOALPOSTS: Final[dict[str, Goalpost]] = {
    # --- Standard goalposts ------------------------------------------------ #
    "SP.DYN.LE00.IN": Goalpost(
        20.0,
        85.0,
        "UNDP Human Development Report 2025, Technical Notes: HDI life-expectancy "
        "goalposts (20 = natural zero, 85 = aspirational target)",
    ),
    "SH.DYN.MORT": Goalpost(
        2.6,
        130.0,
        "Sustainable Development Report 2026, Part 5 indicator table: optimum 2.6 "
        "(SDG-derived), lower bound 130 (2.5th percentile worldwide)",
    ),
    # --- Seeded goalposts -------------------------------------------------- #
    # Observed 2011-2024 range in brackets; bounds rounded outward.
    "NY.GDP.PCAP.KD": Goalpost(
        475.0,
        6_850.0,
        f"{_SEEDED}, in log space [observed 743-4,368]. HDI income goalposts "
        "($100-$75,000) not used: they are for GNI per capita at 2017 PPP, a "
        "different basis from constant-2015-US$ GDP per capita",
    ),
    "NY.GDP.MKTP.KD.ZG": Goalpost(-17.5, 14.5, f"{_SEEDED} [observed -12.0 to 9.0]"),
    "BX.KLT.DINV.WD.GD.ZS": Goalpost(-3.0, 14.5, f"{_SEEDED} [observed 0.1-11.2]"),
    "SI.POV.DDAY": Goalpost(
        0.0, 39.0, f"{_SEEDED} [observed 1.3-31.2]; low clamped at 0 (zero poverty)"
    ),
    "IT.NET.USER.ZS": Goalpost(
        0.0, 100.0, f"{_SEEDED} [observed 1.0-84.2]; clamped to the 0-100% share domain"
    ),
    "IT.CEL.SETS.P2": Goalpost(0.0, 205.0, f"{_SEEDED} [observed 2.5-162.8]; low clamped at 0"),
    "TX.VAL.TECH.MF.ZS": Goalpost(0.0, 55.5, f"{_SEEDED} [observed 0.1-44.3]; low clamped at 0"),
    "SE.SEC.ENRR": Goalpost(
        32.5, 112.5, f"{_SEEDED} [observed 45.8-98.8]; gross ratios can exceed 100"
    ),
    "SH.XPD.CHEX.GD.ZS": Goalpost(0.0, 8.0, f"{_SEEDED} [observed 1.3-6.5]; low clamped at 0"),
}
"""Fixed bounds that put every country-year - past, counterfactual or projected -
on the same ruler.

Where a published standard exists it is used verbatim. Otherwise the bound was
seeded once from the historical range with :data:`GOALPOST_PADDING` and then
**frozen**: it is a constant, not recomputed, so a new data vintage cannot
rewrite historical scores. Re-seed deliberately (see
:func:`amber.modeling.index.seed_goalpost`) only when the indicator set changes.
"""

DEFAULT_PILLAR_WEIGHTS: Final[dict[Pillar, float]] = {
    Pillar.ECONOMY: 1 / 3,
    Pillar.INNOVATION: 1 / 3,
    Pillar.HUMAN_DEVELOPMENT: 1 / 3,
}
"""Equal weighting - where the frontend sliders start, not a claim about what matters."""

NORMALIZED_FLOOR: Final[float] = 0.01
"""Lower clip for normalized scores.

Without a floor, the worst country-year on any indicator scores exactly 0,
and a geometric mean containing a 0 is 0 whatever else is true.
"""

NORMALIZED_CEILING: Final[float] = 1.0

COMBINED_SERIES: Final[str] = "combined"
"""Series label for the combined index, alongside the pillar names."""

INDEX_SERIES: Final[tuple[str, ...]] = (*(str(p) for p in Pillar), COMBINED_SERIES)


def _check_index_config() -> None:
    """Fail at import if the index config drifts out of step with the indicators.

    Raises:
        ValueError: If any indicator lacks a polarity or goalpost, an entry
            names an unknown indicator, the default weights miss a pillar, a
            goalpost is inverted or cannot be logged, or an index exclusion is
            undocumented or empties a pillar.
    """
    configured = set(INDICATORS_BY_ID)
    if set(INDICATOR_POLARITY) != configured:
        missing = sorted(configured - set(INDICATOR_POLARITY))
        extra = sorted(set(INDICATOR_POLARITY) - configured)
        msg = f"INDICATOR_POLARITY out of step: missing {missing}, unknown {extra}"
        raise ValueError(msg)
    if not LOG_TRANSFORM <= configured:
        msg = f"LOG_TRANSFORM names unknown indicators: {sorted(LOG_TRANSFORM - configured)}"
        raise ValueError(msg)
    if set(DEFAULT_PILLAR_WEIGHTS) != set(Pillar):
        msg = "DEFAULT_PILLAR_WEIGHTS must give a weight to every pillar"
        raise ValueError(msg)
    if set(GOALPOSTS) != configured:
        missing = sorted(configured - set(GOALPOSTS))
        extra = sorted(set(GOALPOSTS) - configured)
        msg = f"GOALPOSTS out of step: missing {missing}, unknown {extra}"
        raise ValueError(msg)
    for indicator_id, goalpost in GOALPOSTS.items():
        if not goalpost.low < goalpost.high:
            msg = f"Goalpost for {indicator_id} needs low < high, got {goalpost}"
            raise ValueError(msg)
        if indicator_id in LOG_TRANSFORM and goalpost.low <= 0:
            msg = f"Goalpost for log-transformed {indicator_id} needs low > 0"
            raise ValueError(msg)
    unknown = sorted(set(INDEX_EXCLUDED) - configured)
    if unknown:
        msg = f"INDEX_EXCLUDED names unknown indicators: {unknown}"
        raise ValueError(msg)
    undocumented = sorted(i for i, reason in INDEX_EXCLUDED.items() if not reason)
    if undocumented:
        msg = f"Excluding {undocumented} from the index needs a documented reason"
        raise ValueError(msg)
    indexed_pillars = {PILLAR_BY_INDICATOR[i] for i in INDEX_INDICATORS}
    empty = sorted(str(p) for p in Pillar if p not in indexed_pillars)
    if empty:
        msg = f"INDEX_EXCLUDED leaves pillars with no indicators: {empty}"
        raise ValueError(msg)


_check_index_config()


# --------------------------------------------------------------------------- #
# Synthetic control
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SCOutcome:
    """One outcome the counterfactual is estimated for.

    Attributes:
        name: A WDI indicator id (read from the panel) or an index series name
            (read from index.csv). The source is resolved by where the name is
            found.
        slug: Filename-safe short name for figures.
        label: What the outcome is, for chart titles.
        units: Axis label, including units.
        is_currency: Format values as dollars in charts and annotations.
    """

    name: str
    slug: str
    label: str
    units: str
    is_currency: bool = False


SC_OUTCOMES: Final[tuple[SCOutcome, ...]] = (
    SCOutcome(
        "NY.GDP.PCAP.KD",
        "gdp_pc",
        "Real GDP per capita",
        "GDP per capita, constant 2015 US$",
        is_currency=True,
    ),
    SCOutcome(
        "combined",
        "combined_index",
        "Combined development index",
        "Index points (0.01–1 scale)",
    ),
)
"""GDP per capita is the headline economic result and the densest series across
donors; the combined index is the headline development result."""

SC_PREDICTORS: Final[tuple[str, ...]] = ()
"""Optional covariates (indicator ids), averaged over the fit window.

Empty by default: matching on the pre-treatment outcome path alone is the
transparent choice, and six donors cannot support many features.
"""

SC_PRE_PERIOD_END: Final[int] = TREATMENT_YEAR - 1
"""Last year of the fit window (inclusive).

2020 is kept, deliberately, though it sits in tension with
:data:`COVID_CONFOUNDED_YEARS`. Excluding 2020 matters when attributing a shock
to the coup; here the question is what donors share, and COVID hit them too, so
matching against donors that also absorbed COVID controls for it. The catch is
Myanmar's 2020: WDI assigns fiscal Oct 2019-Sep 2020 to 2020 (entirely pre-coup),
but records -9.1% growth, far below any donor, so it cannot be matched and
inflates pre-RMSE. Set to ``TREATMENT_YEAR - 2`` to test that choice.
"""

SC_REBASE: Final[bool] = False
"""Index each series to 100 at :data:`MODELING_WINDOW_START` before matching.

A robustness variant, not the default: levels matching is standard, and a poor
levels fit is information (the treated unit is outside the donor hull).
"""

SC_MIN_DONORS: Final[int] = 3
"""Fewest donors a fit may use after incomplete ones are dropped."""

SC_N_RESTARTS: Final[int] = 25
"""SLSQP starts per fit: one uniform, the rest Dirichlet draws."""

SC_SEED: Final[int] = 20210201
"""RNG seed for restart draws, so every run gives identical weights."""

SC_INTIME_PLACEBO_YEAR: Final[int] = 2017
"""Fake treatment year for the in-time placebo, fitted on pre-2021 data only."""

SC_WEIGHT_THRESHOLD: Final[float] = 0.01
"""A donor at or above this weight counts as "positively weighted" - the set the
leave-one-out check drops in turn."""

SC_CREDIBLE_PRE_RMSE_SHARE: Final[float] = 0.10
"""Largest pre-RMSE, as a share of the treated unit's mean fit-window level, at
which the post-period gap counts as a credible effect estimate.

Above it the fit is not a weaker estimate but no estimate: a synthetic that
misses the pre-period by that much says nothing about the post-period. The
verdict is recorded as the ``credible`` column of ``sc_metrics`` and drives the
chart captions, so prose and data cannot disagree.
"""

SC_PLACEBO_POOR_FIT_MULTIPLE: Final[float] = 5.0
"""Display only: placebos whose pre-RMSE exceeds this multiple of the treated
unit's are drawn faintly in the gap chart (Abadie et al. 2010). A donor at the
edge of the hull cannot be matched by the others, so its "gap" is a fitting
failure rather than an effect. Inference still uses every unit."""


def _check_synthetic_control_config() -> None:
    """Fail at import if the synthetic-control config is inconsistent.

    Raises:
        ValueError: If an outcome does not resolve or is duplicated, a slug is
            not filename-safe, a predictor is not configured, the years are out
            of order, or the donor settings cannot work.
    """
    names = [outcome.name for outcome in SC_OUTCOMES]
    slugs = [outcome.slug for outcome in SC_OUTCOMES]
    if not SC_OUTCOMES:
        msg = "SC_OUTCOMES is empty"
        raise ValueError(msg)
    if len(set(names)) != len(names) or len(set(slugs)) != len(slugs):
        msg = f"SC_OUTCOMES names and slugs must be unique: {names}, {slugs}"
        raise ValueError(msg)
    for outcome in SC_OUTCOMES:
        in_panel = outcome.name in INDICATORS_BY_ID
        in_index = outcome.name in INDEX_SERIES
        if in_panel == in_index:
            where = "both the panel and the index" if in_panel else "neither source"
            msg = f"SC outcome {outcome.name!r} resolves to {where}"
            raise ValueError(msg)
        if not outcome.slug.replace("_", "").isalnum() or not outcome.slug.islower():
            msg = f"SC outcome slug {outcome.slug!r} must be lowercase alphanumeric/underscore"
            raise ValueError(msg)

    unknown = sorted(set(SC_PREDICTORS) - set(INDICATORS_BY_ID))
    if unknown:
        msg = f"SC_PREDICTORS names unconfigured indicators: {unknown}"
        raise ValueError(msg)

    if not MODELING_WINDOW_START < SC_PRE_PERIOD_END < TREATMENT_YEAR:
        msg = (
            f"SC_PRE_PERIOD_END={SC_PRE_PERIOD_END} must fall after "
            f"{MODELING_WINDOW_START} and before {TREATMENT_YEAR}"
        )
        raise ValueError(msg)
    if not MODELING_WINDOW_START + 1 < SC_INTIME_PLACEBO_YEAR < TREATMENT_YEAR:
        msg = (
            f"SC_INTIME_PLACEBO_YEAR={SC_INTIME_PLACEBO_YEAR} needs at least two fit years "
            f"after {MODELING_WINDOW_START} and must precede {TREATMENT_YEAR}"
        )
        raise ValueError(msg)

    if TREATED_COUNTRY in DONOR_POOL:
        msg = f"{TREATED_COUNTRY} cannot be in its own donor pool"
        raise ValueError(msg)
    if not 2 <= SC_MIN_DONORS <= len(DONOR_POOL) - 1:
        # Placebo fits use the pool minus one, so they need the headroom too.
        msg = f"SC_MIN_DONORS must be between 2 and {len(DONOR_POOL) - 1}, got {SC_MIN_DONORS}"
        raise ValueError(msg)
    if SC_N_RESTARTS < 1:
        msg = "SC_N_RESTARTS must be at least 1"
        raise ValueError(msg)
    if not 0 < SC_WEIGHT_THRESHOLD < 1:
        msg = "SC_WEIGHT_THRESHOLD must be in (0, 1)"
        raise ValueError(msg)
    if SC_CREDIBLE_PRE_RMSE_SHARE <= 0 or SC_PLACEBO_POOR_FIT_MULTIPLE <= 1:
        msg = "SC_CREDIBLE_PRE_RMSE_SHARE must be positive and SC_PLACEBO_POOR_FIT_MULTIPLE above 1"
        raise ValueError(msg)


_check_synthetic_control_config()


# --------------------------------------------------------------------------- #
# System dynamics
# --------------------------------------------------------------------------- #
#
# An annual stock-and-flow model of Myanmar (see amber.modeling.system_dynamics
# for the equations). Everything that shapes it lives here: which parameters are
# fixed and which are calibrated, the levers and their ranges, the scenarios, and
# how model quantities map onto the development index's indicators.

SD_BACKTEST_START: Final[int] = MODELING_WINDOW_START
SD_BACKTEST_END: Final[int] = YEAR_END
"""The calibration window. The backtest is in-sample: the coup's effect cannot be
identified without post-2021 data, so there is no holdout."""

SD_PROJECTION_START: Final[int] = YEAR_END + 1
"""First year scenario levers apply. Policy cannot act retroactively, so levers
start here; stability paths can differ from the treatment year."""

SD_HORIZON_END: Final[int] = 2035

SD_OUTPUT_INDICATOR: Final[str] = "NY.GDP.PCAP.KD"
"""Output Y *is* GDP per capita, which pins the model's scale."""

SD_CONNECTIVITY_INDICATOR: Final[str] = "IT.NET.USER.ZS"
"""Connectivity I is measured in internet users (% of population); its upper
goalpost is the saturation level I_max."""

SD_HUMAN_CAPITAL_INDICATOR: Final[str] = "SP.DYN.LE00.IN"
"""Human capital H is life expectancy relative to its first modeled year (H0 = 1)."""


@dataclass(frozen=True, slots=True)
class SDParameter:
    """One model parameter.

    Attributes:
        value: The fixed value, or the calibration's starting guess.
        low: Lower bound (calibration and ensemble jitter stay inside it).
        high: Upper bound.
        calibrate: Fit to data (True) or hold at ``value`` (False).
        description: What it is, and for fixed ones why that value.
        unidentified: Fixed because the data cannot tell values in
            ``[low, high]`` apart. The central run holds it at ``value``; the
            ensemble spreads across ``low``, ``value`` and ``high``, each with the
            calibrated parameters refitted to history, so the bands carry the
            assumption instead of hiding it.
    """

    value: float
    low: float
    high: float
    calibrate: bool
    description: str
    unidentified: bool = False


SD_PARAMETERS: Final[dict[str, SDParameter]] = {
    # --- Fixed: conventions the data cannot pin down ----------------------- #
    "alpha": SDParameter(
        1 / 3, 1 / 3, 1 / 3, False,
        "Output elasticity of capital; 1/3 as in the Mankiw-Romer-Weil augmented Solow model",
    ),
    "beta": SDParameter(
        1 / 3, 1 / 3, 1 / 3, False,
        "Output elasticity of human capital; 1/3 as in Mankiw-Romer-Weil",
    ),
    "delta_k": SDParameter(
        0.05, 0.05, 0.05, False, "Capital depreciation rate; a conventional 5% a year",
    ),
    "delta_h": SDParameter(
        0.02, 0.02, 0.02, False,
        "Human-capital depreciation; an assumption, set so H approaches a steady state slowly",
    ),
    "delta_i": SDParameter(
        0.02, 0.02, 0.02, False, "Connectivity attrition (lapsed users, obsolete networks)",
    ),
    "covid_persistence": SDParameter(
        1.0, 0.0, 1.0, False,
        "Share of the COVID output loss still present each following year (1 = a "
        "permanent level loss, 0 = a one-year dip). Myanmar's own data cannot tell: "
        "after 2020, COVID and the coup overlap. The donors can: against their "
        "2011-2019 trends they fell 6% short in 2020 and 12% by 2024, and none "
        "recovered - so a one-year dip with a full rebound is contradicted, and the "
        "loss is held permanent. The widening is deliberately not imported, so the "
        "phase 3 consistency check stays independent",
    ),
    "capital_output_ratio": SDParameter(
        2.5, 2.5, 2.5, False, "Initial K/Y; a typical value for a low-income economy",
    ),
    # --- Fixed: not identified by the data --------------------------------- #
    # Profiled 2026-10-01 on Myanmar 2011-2024: refitting everything else with
    # each held fixed, the backtest nRMSE moves by under 0.003 across
    # kappa in [0, 0.5] and s_K in [0.2, 0.5]. Left free, the optimizer takes
    # corners (kappa = 0, s_K = 0.5) because it is indifferent, not because the
    # data choose them. Both are therefore assumptions - and because they are,
    # the ensemble spans those ranges (unidentified=True) and every run re-checks
    # the profile (sd_profile, SD_PROFILE_TOLERANCE).
    "savings_rate": SDParameter(
        0.30, 0.20, 0.50, False,
        "Investment share of output at fdi_openness = 1; a plausible share, "
        "not identified by the data (see profile note)",
        unidentified=True,
    ),
    "connectivity_tfp": SDParameter(
        0.25, 0.0, 0.5, False,
        "kappa: TFP gain at full connectivity - the leapfrog channel, assumed rather "
        "than estimated. 0.25 is the midpoint of the range Myanmar's data cannot tell "
        "apart (see profile note), and conservative against the literature: it is a "
        "one-off level effect of 2.5% per 10 pp of internet users, where Czernich et "
        "al. (2011, Economic Journal 121: 505-532) estimate that 10 pp of broadband "
        "raised annual per-capita growth by 0.9-1.5 pp across the OECD, 1996-2007",
        unidentified=True,
    ),
    # --- Calibrated: dynamics ---------------------------------------------- #
    "stability_elasticity": SDParameter(
        0.5, 0.0, 3.0, True, "gamma: TFP elasticity to institutional stability",
    ),
    "tfp_growth": SDParameter(
        0.01, 0.0, 0.05, True, "Exogenous TFP growth a year",
    ),
    "covid_shock": SDParameter(
        0.08, 0.0, 0.3, True,
        "Share of output lost in COVID_CONFOUNDED_YEARS - kept separate so the model "
        "does not attribute 2020 to the coup",
    ),
    "stability_post": SDParameter(
        0.6, 0.05, 1.0, True,
        "Post-coup stability relative to the reform era (S_pre = 1 by definition)",
    ),
    "human_capital_gain": SDParameter(
        0.025, 0.0, 0.1, True, "g_H: human-capital accumulation at default spending",
    ),
    "connectivity_gain": SDParameter(
        0.5, 0.0, 3.0, True, "phi_I: diffusion rate of connectivity at default investment",
    ),
    # --- Calibrated: links from the model to indicators --------------------- #
    "population_growth": SDParameter(
        0.8, 0.0, 3.0, True,
        "Percentage points separating total GDP growth from per-capita growth",
    ),
    "fdi_scale": SDParameter(4.0, 0.0, 14.0, True, "FDI % of GDP at S = 1, fdi_openness = 1"),
    "mobile_saturation": SDParameter(
        150.0, 20.0, 205.0, True, "Mobile subscriptions per 100 at full diffusion and S = 1",
    ),
    "mobile_scale": SDParameter(
        15.0, 1.0, 100.0, True, "Internet-user level at which mobile reaches 63% of saturation",
    ),
    "mortality_elasticity": SDParameter(
        -9.0, -30.0, 0.0, True, "Elasticity of under-5 mortality to H (negative: H lowers it)",
    ),
    "enrollment_elasticity": SDParameter(
        14.0, 0.0, 60.0, True,
        "How fast secondary enrollment closes the gap to its ceiling as H rises",
    ),
    "health_share": SDParameter(
        4.0, 0.0, 8.0, True, "Health expenditure % of GDP at health_spend = 1",
    ),
}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Lever:
    """A policy setting a scenario (or a phase 5 slider) can move.

    Levers are multipliers on calibrated behaviour: 1.0 reproduces what the
    reform era implies, 1.5 is half as much again.

    Attributes:
        default: The value when a scenario does not set it.
        low: Smallest allowed value.
        high: Largest allowed value.
        description: What it multiplies.
        label: Short name for a slider.
        step: Slider increment; ``low``, ``high`` and ``default`` sit on its grid.
    """

    default: float
    low: float
    high: float
    description: str
    label: str = ""
    step: float = 0.05


LEVERS: Final[dict[str, Lever]] = {
    "fdi_openness": Lever(
        1.0, 0.5, 1.5, "Investment rate and FDI inflows", label="Investment openness"
    ),
    "education_spend": Lever(
        1.0,
        0.5,
        2.0,
        "Human-capital accumulation (with health_spend)",
        label="Education spending",
    ),
    "health_spend": Lever(
        1.0,
        0.5,
        2.0,
        "Human-capital accumulation and health expenditure % of GDP",
        label="Health spending",
    ),
    "connectivity_investment": Lever(
        1.0, 0.5, 2.0, "The diffusion rate of connectivity", label="Connectivity investment"
    ),
}

StabilityPath = tuple[tuple[int, float], ...]
"""``(year, recovery)`` breakpoints, linearly interpolated and held after the last.

Recovery r maps to stability as ``S = S_post + r * (1 - S_post)``: 1 is the
reform-era (pre-coup) level, 0 the calibrated post-coup level. Expressing paths
in r keeps scenarios valid whatever the calibration finds for S_post.
"""

SD_HISTORICAL_STABILITY: Final[StabilityPath] = (
    (MODELING_WINDOW_START, 1.0),
    (TREATMENT_YEAR - 1, 1.0),
    (TREATMENT_YEAR, 0.0),
)
"""What actually happened: reform-era stability until the coup, post-coup after."""


@dataclass(frozen=True, slots=True)
class Scenario:
    """A future to simulate - data, not code.

    Attributes:
        name: Identifier used in tables and file names.
        label: Human-readable name for charts.
        stability: Recovery breakpoints (see :data:`StabilityPath`).
        levers: Lever overrides from :data:`SD_PROJECTION_START`; unset levers
            take their default.
        description: One line on what the scenario represents.
    """

    name: str
    label: str
    stability: StabilityPath
    levers: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def lever(self, name: str) -> float:
        """The scenario's value for a lever, falling back to its default."""
        return self.levers.get(name, LEVERS[name].default)


SCENARIOS: Final[tuple[Scenario, ...]] = (
    Scenario(
        "actual_continuation",
        "Actual continuation",
        SD_HISTORICAL_STABILITY,
        description="Stability stays at the post-coup level; levers unchanged.",
    ),
    Scenario(
        "no_coup",
        "No coup",
        ((MODELING_WINDOW_START, 1.0),),
        description="Reform-era stability throughout - the counterfactual extended forward.",
    ),
    Scenario(
        "partial_recovery",
        "Partial recovery",
        (*SD_HISTORICAL_STABILITY, (YEAR_END, 0.0), (SD_HORIZON_END, 0.5)),
        description="Post-coup stability to 2024, then half the way back by 2035.",
    ),
    Scenario(
        "reform_push",
        "Reform push",
        ((MODELING_WINDOW_START, 1.0),),
        levers={"education_spend": 1.5, "connectivity_investment": 1.5},
        description="No coup, plus the MSDP Strategy 3.7 ambition on education and connectivity.",
    ),
)

SD_BASELINE_SCENARIO: Final[str] = "actual_continuation"
SD_COUNTERFACTUAL_SCENARIO: Final[str] = "no_coup"
"""The scenario checked against the phase 3 synthetic control over the overlap."""


class LinkKind(StrEnum):
    """How an indicator is derived from the model."""

    OUTPUT = "output"
    """x = Y."""
    GROWTH = "growth"
    """x = 100 (Y_t / Y_t-1 - 1) + population_growth."""
    CONNECTIVITY = "connectivity"
    """x = I."""
    HUMAN_CAPITAL = "human_capital"
    """x = x0 H (x0 = first modeled year's value)."""
    ELASTICITY = "elasticity"
    """x = x0 H^elasticity."""
    BOUNDED = "bounded"
    """x = x_max - (x_max - x0) H^-elasticity: rises with H toward the goalpost
    ceiling x_max instead of compounding past it - for shares."""
    SATURATING = "saturating"
    """x = saturation (1 - exp(-I / scale)) S."""
    STABILITY_SHARE = "stability_share"
    """x = scale lever S."""
    LEVER_SHARE = "lever_share"
    """x = scale lever."""


LINK_ARITY: Final[dict[LinkKind, int]] = {
    LinkKind.OUTPUT: 0,
    LinkKind.GROWTH: 1,
    LinkKind.CONNECTIVITY: 0,
    LinkKind.HUMAN_CAPITAL: 0,
    LinkKind.ELASTICITY: 1,
    LinkKind.BOUNDED: 1,
    LinkKind.SATURATING: 2,
    LinkKind.STABILITY_SHARE: 1,
    LinkKind.LEVER_SHARE: 1,
}
"""Parameters each link kind takes."""

LINKS_WITH_LEVER: Final[frozenset[LinkKind]] = frozenset(
    {LinkKind.STABILITY_SHARE, LinkKind.LEVER_SHARE}
)


@dataclass(frozen=True, slots=True)
class IndicatorLink:
    """How one indicator is produced by the model.

    Attributes:
        kind: The functional form.
        params: Names in :data:`SD_PARAMETERS` the form uses, in order.
        lever: The lever it scales with, for lever-driven kinds.
        note: Why this form, where it is not obvious.
    """

    kind: LinkKind
    params: tuple[str, ...] = ()
    lever: str | None = None
    note: str = ""


SD_INDICATOR_LINKS: Final[dict[str, IndicatorLink]] = {
    "NY.GDP.PCAP.KD": IndicatorLink(LinkKind.OUTPUT),
    "NY.GDP.MKTP.KD.ZG": IndicatorLink(LinkKind.GROWTH, ("population_growth",)),
    "BX.KLT.DINV.WD.GD.ZS": IndicatorLink(
        LinkKind.STABILITY_SHARE, ("fdi_scale",), lever="fdi_openness"
    ),
    "IT.NET.USER.ZS": IndicatorLink(LinkKind.CONNECTIVITY),
    "IT.CEL.SETS.P2": IndicatorLink(
        LinkKind.SATURATING,
        ("mobile_saturation", "mobile_scale"),
        note="Saturates well before internet use; scaled by S because subscriptions "
        "fell after 2021 (shutdowns, SIM restrictions)",
    ),
    "SP.DYN.LE00.IN": IndicatorLink(LinkKind.HUMAN_CAPITAL),
    "SH.DYN.MORT": IndicatorLink(LinkKind.ELASTICITY, ("mortality_elasticity",)),
    "SE.SEC.ENRR": IndicatorLink(
        LinkKind.BOUNDED,
        ("enrollment_elasticity",),
        note="A share: a power law compounds past 100% within the horizon, so it "
        "saturates at its goalpost ceiling instead",
    ),
    "SH.XPD.CHEX.GD.ZS": IndicatorLink(
        LinkKind.LEVER_SHARE, ("health_share",), lever="health_spend"
    ),
}
"""How the model produces every index indicator (:data:`INDEX_INDICATORS`), so a
projected index has exactly the composition of the historical one."""

SD_CREDIBLE_NRMSE: Final[float] = 0.10
"""Largest overall backtest nRMSE - on the goalpost scale, so in index units - at
which the scenarios count as a calibrated projection. Above it every caption
calls them illustrative dynamics."""

SD_SC_TOLERANCE: Final[float] = 0.10
"""Largest relative deviation between the no-coup scenario and a credible
synthetic control over the overlap before it is flagged."""

SD_PARAM_JITTER: Final[float] = 0.15
"""Ensemble spread: each calibrated parameter is scaled by a uniform draw in
[1 - jitter, 1 + jitter], clipped to its bounds, around the fit of the member's
profile node (see ``SDParameter.unidentified``)."""

SD_PROFILE_TOLERANCE: Final[float] = 0.01
"""Largest rise in the overall backtest nRMSE, at any profile node of the
unidentified parameters, over the central fit. Beyond it the data do tell the
values apart, so the parameter should be calibrated, not assumed - the run
warns and ``sd_profile`` records ``flat`` false."""

SD_ENSEMBLE_SIZE: Final[int] = 200
"""Members per scenario; member 0 is the unjittered calibration."""

SD_SEED: Final[int] = 20350101
SD_CALIBRATION_RESTARTS: Final[int] = 8
"""Least-squares starts: the defaults, then seeded draws inside the bounds."""

SD_QUANTILES: Final[dict[str, float]] = {"p10": 0.10, "p50": 0.50, "p90": 0.90}

SD_GAP_SERIES: Final[tuple[str, ...]] = (SD_OUTPUT_INDICATOR, COMBINED_SERIES)
"""Series whose paired, member-by-member gap from the baseline scenario is reported."""


def _check_system_dynamics_config(
    *,
    parameters: Mapping[str, SDParameter] = SD_PARAMETERS,
    levers: Mapping[str, Lever] = LEVERS,
    scenarios: Sequence[Scenario] = SCENARIOS,
    links: Mapping[str, IndicatorLink] = SD_INDICATOR_LINKS,
) -> None:
    """Fail at import if the system-dynamics config is inconsistent.

    Takes its inputs as arguments so tests can exercise the same checks on
    deliberately broken configurations.

    Raises:
        ValueError: On out-of-bounds parameters or levers, scenarios that name
            unknown levers or leave the window, a mapping that misses an
            index indicator (or maps one outside it) or misuses a parameter,
            or unusable run settings.
    """
    for name, p in parameters.items():
        if not p.low <= p.value <= p.high:
            msg = f"SD parameter {name}: value {p.value} outside [{p.low}, {p.high}]"
            raise ValueError(msg)
        if p.calibrate and not p.low < p.high:
            msg = f"SD parameter {name} is calibrated but has no room to move"
            raise ValueError(msg)
        if p.unidentified and (p.calibrate or not p.low < p.high):
            msg = f"SD parameter {name}: unidentified needs a fixed value and a range to span"
            raise ValueError(msg)

    for name, lever in levers.items():
        if not lever.low <= lever.default <= lever.high:
            msg = f"Lever {name}: default {lever.default} outside [{lever.low}, {lever.high}]"
            raise ValueError(msg)
        if not lever.label or lever.step <= 0:
            msg = f"Lever {name} needs a label and a positive step"
            raise ValueError(msg)
        for point in (lever.low, lever.high, lever.default):
            steps = (point - lever.low) / lever.step
            if abs(steps - round(steps)) > 1e-9:
                msg = f"Lever {name}: {point} is not on its {lever.step} step grid"
                raise ValueError(msg)

    names = [s.name for s in scenarios]
    if len(set(names)) != len(names):
        msg = f"Scenario names must be unique: {names}"
        raise ValueError(msg)
    for scenario in scenarios:
        unknown = sorted(set(scenario.levers) - set(levers))
        if unknown:
            msg = f"Scenario {scenario.name!r} sets unknown levers: {unknown}"
            raise ValueError(msg)
        for lever_name, value in scenario.levers.items():
            lever = levers[lever_name]
            if not lever.low <= value <= lever.high:
                msg = f"Scenario {scenario.name!r}: {lever_name}={value} outside its range"
                raise ValueError(msg)
        years = [year for year, _ in scenario.stability]
        if not years or years != sorted(years):
            msg = f"Scenario {scenario.name!r}: stability breakpoints must be sorted, non-empty"
            raise ValueError(msg)
        if years[0] > SD_BACKTEST_START or years[-1] > SD_HORIZON_END:
            msg = f"Scenario {scenario.name!r}: stability path must start by {SD_BACKTEST_START}"
            raise ValueError(msg)
        if any(not 0.0 <= r <= 1.0 for _, r in scenario.stability):
            msg = f"Scenario {scenario.name!r}: stability recovery must be in [0, 1]"
            raise ValueError(msg)
    for required in (SD_BASELINE_SCENARIO, SD_COUNTERFACTUAL_SCENARIO):
        if required not in names:
            msg = f"Scenario {required!r} is required but not configured"
            raise ValueError(msg)

    missing = sorted(set(INDEX_INDICATORS) - set(links))
    extra = sorted(set(links) - set(INDEX_INDICATORS))
    if missing or extra:
        msg = (
            f"SD_INDICATOR_LINKS must cover the index indicators: missing {missing}, extra {extra}"
        )
        raise ValueError(msg)
    for indicator_id, link in links.items():
        if len(link.params) != LINK_ARITY[link.kind]:
            msg = f"Link for {indicator_id}: {link.kind} takes {LINK_ARITY[link.kind]} params"
            raise ValueError(msg)
        unknown_params = sorted(set(link.params) - set(parameters))
        if unknown_params:
            msg = f"Link for {indicator_id} names unknown parameters: {unknown_params}"
            raise ValueError(msg)
        if (link.kind in LINKS_WITH_LEVER) != (link.lever is not None):
            msg = f"Link for {indicator_id}: lever must be set exactly for lever-driven kinds"
            raise ValueError(msg)
        if link.lever is not None and link.lever not in levers:
            msg = f"Link for {indicator_id} names unknown lever {link.lever!r}"
            raise ValueError(msg)
    primaries = {
        SD_OUTPUT_INDICATOR: LinkKind.OUTPUT,
        SD_CONNECTIVITY_INDICATOR: LinkKind.CONNECTIVITY,
        SD_HUMAN_CAPITAL_INDICATOR: LinkKind.HUMAN_CAPITAL,
    }
    for indicator_id, kind in primaries.items():
        if links[indicator_id].kind is not kind:
            msg = f"{indicator_id} anchors a stock and must use the {kind} link"
            raise ValueError(msg)
    if not SD_BACKTEST_START < SD_BACKTEST_END < SD_PROJECTION_START <= SD_HORIZON_END:
        msg = "SD years must run backtest start < backtest end < projection start <= horizon"
        raise ValueError(msg)
    if not 0 <= SD_PARAM_JITTER < 1 or SD_ENSEMBLE_SIZE < 1 or SD_CALIBRATION_RESTARTS < 1:
        msg = "SD_PARAM_JITTER must be in [0, 1) and ensemble size and restarts at least 1"
        raise ValueError(msg)
    if SD_CREDIBLE_NRMSE <= 0 or SD_SC_TOLERANCE <= 0 or SD_PROFILE_TOLERANCE <= 0:
        msg = "SD_CREDIBLE_NRMSE, SD_SC_TOLERANCE and SD_PROFILE_TOLERANCE must be positive"
        raise ValueError(msg)


_check_system_dynamics_config()


# --------------------------------------------------------------------------- #
# Source
# --------------------------------------------------------------------------- #

WDI_SOURCE_ID: Final[int] = 2
"""World Bank database id for World Development Indicators.

Pinned so a series is never silently served from a different database with a
different vintage.
"""

FETCH_MAX_ATTEMPTS: Final[int] = 4
FETCH_BACKOFF_SECONDS: Final[float] = 1.5
"""Base for exponential backoff between retries: 1.5s, 3s, 6s, ..."""


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

COL_INDICATOR_ID: Final[str] = "indicator_id"
COL_INDICATOR_NAME: Final[str] = "indicator_name"
COL_PILLAR: Final[str] = "pillar"
COL_COUNTRY_ISO3: Final[str] = "country_iso3"
COL_COUNTRY_NAME: Final[str] = "country_name"
COL_YEAR: Final[str] = "year"
COL_VALUE: Final[str] = "value"
COL_PRE_2011: Final[str] = "pre_2011"
COL_IMPUTED: Final[str] = "imputed"
COL_SERIES: Final[str] = "series"
COL_COVERAGE: Final[str] = "coverage"
COL_NORMALIZED: Final[str] = "normalized"
COL_OUTCOME: Final[str] = "outcome"
COL_DONOR_ISO3: Final[str] = "donor_iso3"
COL_DONOR_NAME: Final[str] = "donor_name"
COL_WEIGHT: Final[str] = "weight"
COL_UNIT_ISO3: Final[str] = "unit_iso3"
COL_GAP: Final[str] = "gap"
COL_DROPPED_DONOR: Final[str] = "dropped_donor"
COL_SCENARIO: Final[str] = "scenario"
COL_QUANTILE: Final[str] = "quantile"
COL_LEVER: Final[str] = "lever"
COL_PARAMETER: Final[str] = "parameter"
COL_SCOPE: Final[str] = "scope"

INGESTION_COLUMNS: Final[tuple[str, ...]] = (
    COL_INDICATOR_ID,
    COL_INDICATOR_NAME,
    COL_COUNTRY_ISO3,
    COL_COUNTRY_NAME,
    COL_YEAR,
    COL_VALUE,
)
"""Schema produced by :mod:`amber.ingestion`."""

PANEL_COLUMNS: Final[tuple[str, ...]] = (
    COL_INDICATOR_ID,
    COL_INDICATOR_NAME,
    COL_PILLAR,
    COL_COUNTRY_ISO3,
    COL_COUNTRY_NAME,
    COL_YEAR,
    COL_VALUE,
    COL_PRE_2011,
)
"""Schema produced by :mod:`amber.cleaning` - ingestion plus pillar and pre_2011."""

PANEL_SORT_KEYS: Final[tuple[str, ...]] = (COL_INDICATOR_ID, COL_COUNTRY_ISO3, COL_YEAR)

INDEX_COLUMNS: Final[tuple[str, ...]] = (
    COL_COUNTRY_ISO3,
    COL_COUNTRY_NAME,
    COL_YEAR,
    COL_SERIES,
    COL_VALUE,
    COL_COVERAGE,
)
"""Schema produced by :func:`amber.modeling.index.compute_index`.

``coverage`` is the share of the series' indicators observed in that
country-year: out of the pillar's indicators for a pillar row, out of every
indicator for a combined row.
"""


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

PANEL_STEM: Final[str] = "panel"
PANEL_INTERPOLATED_STEM: Final[str] = "panel_interpolated"
COVERAGE_REPORT_STEM: Final[str] = "coverage_report"
INDEX_STEM: Final[str] = "index"

REPORTS_DIR: Final[Path] = PROJECT_ROOT / "reports"
FIGURES_DIR: Final[Path] = REPORTS_DIR / "figures"
"""Rendered charts. Committed, unlike data/processed, so they show on GitHub."""

FIGURE_COMBINED_ALL: Final[str] = "combined_index_all_countries.png"
FIGURE_MYANMAR_PILLARS: Final[str] = "myanmar_pillars.png"
FIGURE_GDP_PC_DIVERGENCE: Final[str] = "gdp_pc_divergence.png"

SC_STEM: Final[str] = "synthetic_control"
SC_WEIGHTS_STEM: Final[str] = "sc_weights"
SC_PLACEBO_STEM: Final[str] = "sc_placebo"
SC_PLACEBO_TIME_STEM: Final[str] = "sc_placebo_time"
SC_LEAVE_ONE_OUT_STEM: Final[str] = "sc_leave_one_out"
SC_METRICS_STEM: Final[str] = "sc_metrics"

SC_FIGURE_ACTUAL: Final[str] = "sc_{slug}_actual_vs_synthetic.png"
SC_FIGURE_GAPS: Final[str] = "sc_{slug}_placebo_gaps.png"
SC_FIGURE_WEIGHTS: Final[str] = "sc_{slug}_weights.png"
"""Per-outcome figure names; ``{slug}`` is :attr:`SCOutcome.slug`."""

SD_TRAJECTORY_STEM: Final[str] = "sd_trajectory"
SD_SCENARIOS_STEM: Final[str] = "sd_scenarios"
SD_CALIBRATION_STEM: Final[str] = "sd_calibration"
SD_METRICS_STEM: Final[str] = "sd_metrics"
SD_PROFILE_STEM: Final[str] = "sd_profile"
SD_GAPS_STEM: Final[str] = "sd_gaps"

SD_FIGURE_FAN: Final[str] = "sd_combined_index_fan.png"
SD_FIGURE_GDP: Final[str] = "sd_gdp_pc_scenarios.png"
SD_FIGURE_BACKTEST: Final[str] = "sd_backtest.png"
SD_FIGURE_STOCKS: Final[str] = "sd_stocks.png"

GDP_PC_INDICATOR: Final[str] = "NY.GDP.PCAP.KD"
"""The income series charted directly in the divergence figure."""

SOURCE_NOTE: Final[str] = "Source: World Bank WDI"

OUTPUT_FORMATS: Final[tuple[str, ...]] = ("csv", "parquet")
"""Every processed table is written in both formats: csv to read, parquet to load."""


# --------------------------------------------------------------------------- #
# Release snapshot and API (phase 5)
# --------------------------------------------------------------------------- #

RELEASE_STEMS: Final[tuple[str, ...]] = (
    PANEL_INTERPOLATED_STEM,
    COVERAGE_REPORT_STEM,
    INDEX_STEM,
    SC_STEM,
    SC_WEIGHTS_STEM,
    SC_PLACEBO_STEM,
    SC_PLACEBO_TIME_STEM,
    SC_LEAVE_ONE_OUT_STEM,
    SC_METRICS_STEM,
    SD_TRAJECTORY_STEM,
    SD_SCENARIOS_STEM,
    SD_CALIBRATION_STEM,
    SD_METRICS_STEM,
    SD_PROFILE_STEM,
    SD_GAPS_STEM,
    "historical",
    "historical_divergence",
    "historical_divergence_metrics",
    "historical_divergence_sensitivity",
)
"""Tables the API serves, copied as csv into :data:`RELEASE_DATA_DIR`. The panel
and calibration let it recompute the two live views without any fitting. The
four historical tables (phase 7) are served as-is: nothing in that layer is
user-parameterized. Their stems are spelled out here because the historical
config is defined further down; ``_check_historical_config`` asserts they match."""

RELEASE_MANIFEST: Final[str] = "manifest.json"
"""Provenance for the snapshot: build time, commit, and a hash of every file."""


class DataSource(StrEnum):
    """Where the API reads its tables from (``AMBER_DATA_SOURCE``)."""

    RELEASE = "release"
    """The committed snapshot - reproducible, the production default."""
    PROCESSED = "processed"
    """The working outputs of ``make models`` - for local development."""


DEFAULT_DATA_SOURCE: Final[DataSource] = DataSource.RELEASE

API_DEFAULT_CORS_ORIGINS: Final[tuple[str, ...]] = ("http://localhost:5173",)
"""Allowed origins when ``AMBER_CORS_ORIGINS`` is unset: the Vite dev server."""

API_PANEL_DEFAULT_INDICATORS: Final[tuple[str, ...]] = (GDP_PC_INDICATOR,)
"""What ``GET /panel`` returns when no indicators are named: the divergence chart."""

API_SIMULATE_CACHE_SIZE: Final[int] = 128
"""Live simulations memoized per (scenario, levers), so slider jitter is free."""

API_CACHE_MAX_AGE_SECONDS: Final[int] = 600
"""Browser cache lifetime for the GET endpoints. Their answers change only when a
new snapshot is deployed, and the ETag makes revalidation after expiry cheap. It is
kept short so a redeploy that changes ``/meta`` reaches open tabs within minutes."""

API_GZIP_MINIMUM_BYTES: Final[int] = 1024
"""Responses at least this large are gzip-compressed (``/scenarios`` is ~110 kB raw)."""

PROJECT_FRAMING: Final[str] = (
    "Amber is an analytical instrument, not an argument. It treats the February 2021 "
    "coup as a documented event with measurable consequences and takes no partisan "
    "stance. Its assumptions - the donor pool, the index weights, the lever ranges - "
    "are surfaced as settings rather than baked in."
)
SCENARIO_FRAMING: Final[str] = (
    "Scenarios, not forecasts: each shows how the model's assumptions play out, not "
    "what will happen."
)
SD_NOT_CREDIBLE_MESSAGE: Final[str] = (
    "Illustrative dynamics, not a calibrated projection: the model's backtest error "
    "exceeds its credibility threshold."
)
SC_NOT_CREDIBLE_MESSAGE: Final[str] = (
    "This gap is not a credible effect estimate: synthetic Myanmar does not track real "
    "Myanmar before the coup, so the chart is illustrative only."
)
FISCAL_YEAR_MESSAGE: Final[str] = (
    "Myanmar's WDI year runs October-September, so 2021 includes four pre-coup months."
)
COVERAGE_MESSAGE: Final[str] = (
    "Hollow points are computed from fewer than all index indicators; part of any "
    "movement there is a change of composition, not of development."
)
SC_CHECK_OFF_PATH_TEMPLATE: Final[str] = (
    "This scenario leaves the no-coup path before {year}, so the synthetic control is "
    "not its reference."
)
"""Why a scenario is not compared with the phase 3 synthetic control; ``{year}`` is
the year after the overlap ends."""
SC_CHECK_NOT_CREDIBLE_MESSAGE: Final[str] = (
    "The synthetic control for this outcome is not credible, so it is no reference."
)
CUSTOM_SCENARIO_LABEL: Final[str] = "{base}, custom levers"
CUSTOM_SCENARIO_DESCRIPTION: Final[str] = "{base} Levers set by the user."
"""A live run's label and description, from the scenario its levers override."""


# --------------------------------------------------------------------------- #
# Historical layer (phase 7)
# --------------------------------------------------------------------------- #
#
# A descriptive reconstruction back to 1960 plus one assumption-based divergence
# scenario. Nothing here is fitted, and nothing here feeds the 2011+ panel, the
# index, the synthetic control or the system-dynamics model: the historical
# layer reads its own pulls and writes its own tables.
#
# Three rulers are kept apart and never spliced into one series:
#   1. WDI constant-2015-US$ GDP per capita - the spine from 1960;
#   2. WDI current US$ - excluded outright (see HISTORICAL_RULER_EXCLUDED);
#   3. Maddison Project PPP (2011 int$) - pre-1960 only, under its own indicator
#      id and source tag, drawn on its own axis.

HISTORICAL_START: Final[int] = 1960
"""First year of the historical layer - the first year WDI publishes.

Distinct from :data:`MODELING_WINDOW_START` on purpose: the historical layer is
descriptive, so it may show the military-era years no model is fitted to. The
combined index stays 2011+.
"""

HISTORICAL_END: Final[int] = YEAR_END

HISTORICAL_COMPARATORS: Final[dict[str, str]] = {"THA": "Thailand"}
"""Countries fetched for the long-run story beyond Myanmar and the donor pool.

Thailand: Myanmar's neighbour, a rice-exporting agrarian economy at the start of
the period, with an unbroken WDI series from 1960. It is not a "no-coup" country -
it had its own in 1971, 1976, 1977, 1991, 2006 and 2014 - so tracking it is a path
a neighbour actually took, not a world without military rule.
"""

HISTORICAL_COUNTRIES: Final[dict[str, str]] = {**COUNTRIES, **HISTORICAL_COMPARATORS}
"""Every country the historical layer fetches, as ISO3 -> display name."""

HISTORICAL_COUNTRY_CODES: Final[tuple[str, ...]] = tuple(HISTORICAL_COUNTRIES)

HISTORICAL_EXTRA_CANDIDATES: Final[dict[str, str]] = {"SP.POP.TOTL": "Population, total"}
"""Series checked for long coverage that are not panel indicators (they feed no
pillar, so they are not :class:`Indicator` entries)."""

CURRENT_USD_SUFFIX: Final[str] = ".CD"
"""WDI's code suffix for current-US$ series (``.KD`` is constant US$)."""

HISTORICAL_RULER_EXCLUDED: Final[dict[str, str]] = {
    "NY.GDP.PCAP.CD": "Current US$: until the 2010s Myanmar's kyat was converted at an "
    "official peg (about 6 kyat per dollar) far above its market value, so pre-1990 "
    "dollar levels are an exchange-rate artifact rather than a measure of output",
    "BX.KLT.DINV.WD.GD.ZS": "Its denominator is GDP in current US$, the same peg artifact; "
    "WDI has pre-2000 values for Myanmar (from 1971), but the ratio cannot be read on the "
    "constant-price ruler the historical layer uses",
}
"""Series kept out of the historical layer whatever their coverage, with why.
They are never fetched; the coverage report lists them as ``excluded_ruler``."""

HISTORICAL_COVERAGE_BEFORE: Final[int] = YEAR_START
"""Coverage discovery counts observations before this year - the panel's start -
so "extends" means real data the panel does not already hold."""

HISTORICAL_MIN_OBSERVATIONS: Final[int] = 20
"""Fewest non-zero treated-country observations before
:data:`HISTORICAL_COVERAGE_BEFORE` for a series to extend back (half of 1960-1999).

Zeros do not count: WDI records 0 mobile subscriptions (and 0 internet users)
for years before the technology existed, which marks absence rather than
measuring anything - counting them would extend those series on a flat line.
"""


class CoverageStatus(StrEnum):
    """What coverage discovery decided for one candidate series."""

    EXTENDS = "extends"
    """Enough real pre-2000 data: in ``historical.csv`` from 1960."""
    INSUFFICIENT = "insufficient"
    """Too few real observations before 2000: left out."""
    EXCLUDED_RULER = "excluded_ruler"
    """A current-US$ ruler, excluded without being fetched."""


class Reliability(StrEnum):
    """How far a historical observation can be trusted."""

    LOW = "low"
    """Junta-era national accounts, widely considered unreliable. Drawn with a
    low-reliability cue wherever charted."""
    STANDARD = "standard"
    """No layer-specific concern beyond the usual WDI caveats."""


RELIABILITY_LOW_BEFORE: Final[dict[str, int]] = {TREATED_COUNTRY: 1990}
"""Country -> first year rated standard; its earlier observations are ``low``.

Myanmar before 1990: socialist-era and early-SLORC national accounts, compiled
under controlled prices and a fixed exchange rate, are widely considered
unreliable. The rule is applied per country-year, to every source - Maddison too.
"""


class HistoricalSource(StrEnum):
    """Which ruler a historical row is measured on - never mixed in one series."""

    WB_CONSTANT = "wb_constant"
    """World Bank WDI in real units: constant 2015 US$ for money, physical units
    (years, rates, people) otherwise. No current-US$ series enters."""
    MADDISON = "maddison"
    """Maddison Project Database 2023, GDP per capita in 2011 int$ (PPP)."""


MADDISON_PATH: Final[Path] = DATA_DIR / "external" / "maddison_myanmar.csv"
"""Optional user export of Myanmar's rows from MPD 2023 ``mpd2023_web.xlsx``
(see ``data/external/README.md``). If absent, the layer skips it and logs why."""

MADDISON_INDICATOR: Final[str] = "maddison.gdppc"
"""Indicator id for Maddison rows: deliberately not ``NY.GDP.PCAP.KD``, so the
two rulers cannot be merged into one series by a groupby on indicator."""

MADDISON_INDICATOR_NAME: Final[str] = "GDP per capita (2011 int$, PPP; Maddison Project 2023)"

MADDISON_COLUMNS: Final[tuple[str, str, str]] = ("countrycode", "year", "gdppc")
"""Columns read from the export, named as in the MPD ``Full data`` sheet."""

MADDISON_LAST_YEAR: Final[int] = HISTORICAL_START - 1
"""Maddison rows are kept only before the WDI spine starts. The two never
overlap, so no chart or table can splice them or compare them year by year."""

MADDISON_CITATION: Final[str] = (
    "Maddison Project Database, version 2023 (Bolt and van Zanden 2024), CC BY 4.0"
)


@dataclass(frozen=True, slots=True)
class HistoricalEvent:
    """A dated marker on the historical charts.

    Labels state what happened, neutrally; they claim nothing about effects.
    """

    year: int
    label: str


HISTORICAL_EVENTS: Final[tuple[HistoricalEvent, ...]] = (
    HistoricalEvent(1962, "1962 coup"),
    HistoricalEvent(1987, "1987 UN LDC status"),
    HistoricalEvent(1988, "1988 uprising"),
    HistoricalEvent(MODELING_WINDOW_START, "2011 reforms"),
    HistoricalEvent(TREATMENT_YEAR, "2021 coup"),
)


@dataclass(frozen=True, slots=True)
class DivergenceComparator:
    """Whose growth a divergence scenario borrows.

    Attributes:
        label: Display name.
        units: ISO3 codes whose growth is averaged each year. One unit is that
            country's own growth; several are their mean log growth over the
            units observed in both years, so the composition can change - it is
            recorded per year as ``n_units``.
    """

    label: str
    units: tuple[str, ...]


DIVERGENCE_COMPARATORS: Final[dict[str, DivergenceComparator]] = {
    "THA": DivergenceComparator("Thailand", ("THA",)),
    "donor_average": DivergenceComparator("Donor-pool average", tuple(DONOR_POOL)),
}


@dataclass(frozen=True, slots=True)
class DivergenceScenario:
    """A long-run divergence scenario: an illustration, not an estimate.

    Myanmar's actual GDP per capita at ``anchor_year``, grown forward at the
    comparator's actual annual growth::

        P(anchor) = Y_MMR(anchor)
        P(t)      = P(t-1) * exp(g_t),   g_t = mean over units u of ln(Y_u,t / Y_u,t-1)

    For one comparator country this is ``Y_MMR(anchor) * Y_C(t) / Y_C(anchor)``.
    It answers "where would Myanmar be had it tracked <comparator> since
    <anchor>?" - a question that bundles every difference between the two
    countries (policy, conflict, geography, prices, luck), so it attributes the
    gap to no cause. Unlike the phase 3 synthetic control it is not fitted, so it
    carries no p-value and no credibility verdict.

    Attributes:
        name: Identifier used in tables.
        comparator: Key into :data:`DIVERGENCE_COMPARATORS`.
        anchor_year: The year the path starts at Myanmar's actual level.
    """

    name: str
    comparator: str
    anchor_year: int


DIVERGENCE_SCENARIOS: Final[tuple[DivergenceScenario, ...]] = (
    DivergenceScenario("track_thailand", "THA", HISTORICAL_START),
    DivergenceScenario("track_donor_average", "donor_average", HISTORICAL_START),
)
DIVERGENCE_DEFAULT_SCENARIO: Final[str] = "track_thailand"
"""The scenario charted; every configured one is tabulated."""

DIVERGENCE_SENSITIVITY_ANCHORS: Final[tuple[int, ...]] = (1962, 1988, 1990, YEAR_START)
"""Alternative anchors every scenario is re-run from: the 1962 coup, the 1988
takeover, the first standard-reliability year and the panel's start.

Required, not optional: the result turns on the anchor. On WDI's ruler Myanmar
fell far behind Thailand before 1988 and outgrew it afterwards (on official
figures, the 2000s' contested double-digit rates included), so the latest-year
ratio is above 1 from a 1960 anchor and well below 1 from 1990. The chart states
the range, and ``historical_divergence_sensitivity`` tabulates it.
"""

DIVERGENCE_FRAMING: Final[str] = (
    "Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a "
    "comparator's actual growth rates. It shows how far the two paths diverged, not "
    "what any event cost."
)
LOW_RELIABILITY_MESSAGE: Final[str] = (
    "Myanmar before 1990: junta-era national accounts, widely considered unreliable."
)
HISTORICAL_FISCAL_YEAR_MESSAGE: Final[str] = (
    "Myanmar is reported on its fiscal-year basis, which moved from April-March to "
    "October-September in 2018."
)
CHAINED_LEVEL_MESSAGE: Final[str] = (
    "Constant-price levels are chained back from 2015 through every reported growth rate, "
    "so doubtful growth anywhere - the official double-digit rates of the 2000s included - "
    "moves the 1960 anchor."
)
RULERS_MESSAGE: Final[str] = (
    "Constant 2015 US$ throughout; current-US$ series are excluded (exchange-rate artifact)."
)
MADDISON_RULER_MESSAGE: Final[str] = (
    "Before 1960: Maddison PPP (2011 int$), a different ruler on its own axis"
)
"""Footer note, added only when Maddison rows are actually drawn - so a chart
without them never implies pre-1960 data exists."""
MODELING_WINDOW_MESSAGE: Final[str] = (
    f"The bracket marks the modeling window ({MODELING_WINDOW_START} on): a scope choice for "
    "the index, counterfactual and scenarios, not a data-quality flag - that is the hatching."
)
"""Reliability and modeling scope are separate concepts with separate cues:
hatching (pre-1990, the measurements are suspect) and a bracket (2011+, where
the models are calibrated). Never merge them."""

DIVERGENCE_POINTER_MESSAGE: Final[str] = (
    "For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: "
    "a fitted synthetic control with placebo tests, scoped to 2021-2024."
)
"""Shown beside the divergence scenario so the two are never confused."""
DIVERGENCE_NO_INFERENCE_MESSAGE: Final[str] = (
    "Nothing is fitted, so there is no p-value or credibility check."
)
DIVERGENCE_ANCHOR_TEMPLATE: Final[str] = "The path starts at Myanmar's actual {year} level."
DIVERGENCE_ANCHOR_LOW_TEMPLATE: Final[str] = (
    "The path starts at Myanmar's actual {year} level, itself low reliability."
)
"""The divergence note on where the path starts; the second when the anchor year is
itself flagged low reliability."""

COL_SOURCE: Final[str] = "source"
COL_RELIABILITY: Final[str] = "reliability"

HISTORICAL_COLUMNS: Final[tuple[str, ...]] = (
    COL_COUNTRY_ISO3,
    COL_YEAR,
    COL_INDICATOR_ID,
    COL_VALUE,
    COL_SOURCE,
    COL_RELIABILITY,
)
"""Schema of ``historical.csv`` - tidy, and separate from the 2011+ panel."""

HISTORICAL_STEM: Final[str] = "historical"
HISTORICAL_COVERAGE_STEM: Final[str] = "historical_coverage"
HISTORICAL_DIVERGENCE_STEM: Final[str] = "historical_divergence"
HISTORICAL_DIVERGENCE_METRICS_STEM: Final[str] = "historical_divergence_metrics"
HISTORICAL_DIVERGENCE_SENSITIVITY_STEM: Final[str] = "historical_divergence_sensitivity"

HISTORICAL_FIGURE_GDP: Final[str] = "historical_gdp_pc.png"
HISTORICAL_FIGURE_DIVERGENCE: Final[str] = "historical_divergence.png"


def _check_historical_config(
    *,
    start: int = HISTORICAL_START,
    end: int = HISTORICAL_END,
    countries: Mapping[str, str] = HISTORICAL_COUNTRIES,
    comparators: Mapping[str, DivergenceComparator] = DIVERGENCE_COMPARATORS,
    scenarios: Sequence[DivergenceScenario] = DIVERGENCE_SCENARIOS,
    default_scenario: str = DIVERGENCE_DEFAULT_SCENARIO,
    sensitivity_anchors: Sequence[int] = DIVERGENCE_SENSITIVITY_ANCHORS,
    reliability: Mapping[str, int] = RELIABILITY_LOW_BEFORE,
    candidates: Sequence[str] = (*INDICATORS_BY_ID, *HISTORICAL_EXTRA_CANDIDATES),
    ruler_excluded: Mapping[str, str] = HISTORICAL_RULER_EXCLUDED,
    events: Sequence[HistoricalEvent] = HISTORICAL_EVENTS,
) -> None:
    """Fail at import if the historical config is inconsistent.

    Takes its inputs as arguments so tests can feed it broken configurations.

    Raises:
        ValueError: If the historical window does not precede the modeling
            window, a comparator or scenario does not resolve, an anchor is out
            of range, the reliability rule is missing or out of range, a
            current-US$ candidate is not excluded, or an event is outside the window.
    """
    if not start < YEAR_START <= MODELING_WINDOW_START < end:
        msg = (
            f"The historical window must start before the panel ({YEAR_START}) and the "
            f"modeling window ({MODELING_WINDOW_START}); got {start}-{end}"
        )
        raise ValueError(msg)
    if not MADDISON_LAST_YEAR < start:
        msg = "Maddison rows must end before the WDI spine starts"
        raise ValueError(msg)

    for key, comparator in comparators.items():
        unknown = sorted(set(comparator.units) - set(countries))
        if not comparator.units or unknown or TREATED_COUNTRY in comparator.units:
            msg = f"Comparator {key!r} must name fetched countries other than {TREATED_COUNTRY}"
            raise ValueError(msg)

    names = [s.name for s in scenarios]
    if len(set(names)) != len(names) or default_scenario not in names:
        msg = f"Divergence scenarios must be unique and include {default_scenario!r}: {names}"
        raise ValueError(msg)
    for scenario in scenarios:
        if scenario.comparator not in comparators:
            msg = f"Divergence scenario {scenario.name!r} names an unknown comparator"
            raise ValueError(msg)
        if not start <= scenario.anchor_year < end:
            msg = f"Divergence scenario {scenario.name!r}: anchor outside [{start}, {end})"
            raise ValueError(msg)
    if any(not start <= year < end for year in sensitivity_anchors):
        msg = f"Divergence sensitivity anchors must lie in [{start}, {end})"
        raise ValueError(msg)

    if not reliability:
        msg = "RELIABILITY_LOW_BEFORE must define the low-reliability rule"
        raise ValueError(msg)
    for iso3, cutoff in reliability.items():
        if iso3 not in countries or not start < cutoff <= end:
            msg = f"Reliability rule for {iso3!r}: unknown country or cutoff {cutoff} out of range"
            raise ValueError(msg)

    current = {c for c in candidates if c.endswith(CURRENT_USD_SUFFIX)}
    unexcluded = sorted(current - set(ruler_excluded))
    if unexcluded:
        msg = f"Current-US$ series must be ruler-excluded from the historical layer: {unexcluded}"
        raise ValueError(msg)
    if any(not reason for reason in ruler_excluded.values()):
        msg = "Every ruler exclusion needs a documented reason"
        raise ValueError(msg)

    years = [event.year for event in events]
    if years != sorted(years) or any(not start <= y <= end for y in years):
        msg = "Historical events must be sorted and inside the historical window"
        raise ValueError(msg)
    if not 0 < HISTORICAL_MIN_OBSERVATIONS <= HISTORICAL_COVERAGE_BEFORE - start:
        msg = "HISTORICAL_MIN_OBSERVATIONS must fit inside the pre-panel window"
        raise ValueError(msg)
    served = {
        HISTORICAL_STEM,
        HISTORICAL_DIVERGENCE_STEM,
        HISTORICAL_DIVERGENCE_METRICS_STEM,
        HISTORICAL_DIVERGENCE_SENSITIVITY_STEM,
    }
    if not served <= set(RELEASE_STEMS):
        msg = f"RELEASE_STEMS must carry the served historical tables: {sorted(served)}"
        raise ValueError(msg)


_check_historical_config()

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
from dataclasses import dataclass
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
            names an unknown indicator, the default weights miss a pillar, or a
            goalpost is inverted or cannot be logged.
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

SC_POOR_FIT_SHARE: Final[float] = 0.10
"""Pre-RMSE as a share of the treated unit's mean fit-window level above which the
fit is called poor. A synthetic that misses the pre-period by this much cannot
support reading the post-period gap as an effect, and the charts say so."""

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
    if SC_POOR_FIT_SHARE <= 0 or SC_PLACEBO_POOR_FIT_MULTIPLE <= 1:
        msg = "SC_POOR_FIT_SHARE must be positive and SC_PLACEBO_POOR_FIT_MULTIPLE above 1"
        raise ValueError(msg)


_check_synthetic_control_config()


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

GDP_PC_INDICATOR: Final[str] = "NY.GDP.PCAP.KD"
"""The income series charted directly in the divergence figure."""

SOURCE_NOTE: Final[str] = "Source: World Bank WDI"

OUTPUT_FORMATS: Final[tuple[str, ...]] = ("csv", "parquet")
"""Every processed table is written in both formats: csv to read, parquet to load."""

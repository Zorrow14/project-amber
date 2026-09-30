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


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

PANEL_STEM: Final[str] = "panel"
PANEL_INTERPOLATED_STEM: Final[str] = "panel_interpolated"
COVERAGE_REPORT_STEM: Final[str] = "coverage_report"

OUTPUT_FORMATS: Final[tuple[str, ...]] = ("csv", "parquet")
"""Every processed table is written in both formats: csv to read, parquet to load."""

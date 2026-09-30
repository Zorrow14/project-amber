"""Shared fixtures. Nothing here touches the network."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import pytest

from amber import config

# Three indicators, one per pillar, so pillar mapping is exercised end to end.
GDP = "NY.GDP.PCAP.KD"
INTERNET = "IT.NET.USER.ZS"
LIFE_EXPECTANCY = "SP.DYN.LE00.IN"

TEST_INDICATOR_IDS = (GDP, INTERNET, LIFE_EXPECTANCY)
TEST_COUNTRIES = ("MMR", "VNM")
TEST_YEARS = (2009, 2010, 2011, 2012, 2013)

# value = None means "missing", and each series is shaped to exercise one case:
#   MMR/GDP        - an interior gap, which interpolation should bridge
#   MMR/INTERNET   - a trailing gap, which must NOT be extrapolated
#   VNM/LIFE_EXP   - a leading gap, which must NOT be back-filled
_SERIES: dict[tuple[str, str], tuple[float | None, ...]] = {
    ("MMR", GDP): (1000.0, 1100.0, None, 1300.0, 1400.0),
    ("MMR", INTERNET): (0.2, 0.5, 1.0, None, None),
    ("MMR", LIFE_EXPECTANCY): (64.0, 64.5, 65.0, 65.5, 66.0),
    ("VNM", GDP): (2000.0, 2100.0, 2200.0, 2300.0, 2400.0),
    ("VNM", INTERNET): (26.0, 30.0, 35.0, 39.0, 43.0),
    ("VNM", LIFE_EXPECTANCY): (None, 73.0, 73.5, 74.0, 74.5),
}


@pytest.fixture
def raw_frame() -> pd.DataFrame:
    """A small synthetic frame matching the ingestion output schema.

    Two countries x three indicators x five years, spanning the 2011 boundary
    and including leading, interior and trailing missing values.
    """
    rows = [
        {
            config.COL_INDICATOR_ID: indicator_id,
            config.COL_INDICATOR_NAME: config.INDICATORS_BY_ID[indicator_id].name,
            config.COL_COUNTRY_ISO3: iso3,
            config.COL_COUNTRY_NAME: config.COUNTRIES[iso3],
            config.COL_YEAR: year,
            config.COL_VALUE: value,
        }
        for (iso3, indicator_id), values in _SERIES.items()
        for year, value in zip(TEST_YEARS, values, strict=True)
    ]
    return pd.DataFrame(rows, columns=list(config.INGESTION_COLUMNS))


class FakeSource:
    """An :class:`~amber.ingestion.IndicatorSource` that never hits the network.

    Records every call so tests can assert on cache behaviour.

    Args:
        frame: Ingestion-shaped data to serve, sliced per requested indicator.
    """

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame
        self.calls: list[str] = []

    def fetch(
        self,
        indicator_id: str,
        countries: Sequence[str],
        year_start: int,
        year_end: int,
    ) -> pd.DataFrame:
        """Return the stored rows for one indicator, in source schema."""
        self.calls.append(indicator_id)
        subset = self._frame[
            (self._frame[config.COL_INDICATOR_ID] == indicator_id)
            & (self._frame[config.COL_COUNTRY_ISO3].isin(list(countries)))
            & (self._frame[config.COL_YEAR].between(year_start, year_end))
        ]
        return subset[[config.COL_COUNTRY_ISO3, config.COL_YEAR, config.COL_VALUE]].reset_index(
            drop=True
        )


@pytest.fixture
def fake_source(raw_frame: pd.DataFrame) -> FakeSource:
    """A source serving the synthetic frame instead of calling wbgapi."""
    return FakeSource(raw_frame)

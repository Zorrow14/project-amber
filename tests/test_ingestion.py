"""Ingestion tests. The World Bank client is never called - a fake source stands in."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from amber import config, ingestion
from tests.conftest import GDP, INTERNET, LIFE_EXPECTANCY, FakeSource


@pytest.fixture
def indicator() -> config.Indicator:
    """The GDP per capita series."""
    return config.INDICATORS_BY_ID[GDP]


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


def test_fetch_indicator_returns_the_ingestion_schema(tmp_path, fake_source, indicator):
    frame = ingestion.fetch_indicator(
        indicator,
        source=fake_source,
        countries=("MMR", "VNM"),
        year_start=2009,
        year_end=2013,
        cache_dir=tmp_path,
    )

    assert tuple(frame.columns) == config.INGESTION_COLUMNS
    assert len(frame) == 10  # 2 countries x 5 years
    assert frame[config.COL_INDICATOR_ID].unique().tolist() == [GDP]
    assert frame[config.COL_YEAR].dtype.kind == "i"


def test_fetch_indicator_labels_from_config_not_the_api(tmp_path, fake_source, indicator):
    """Country and indicator names stay stable across source vintages."""
    frame = ingestion.fetch_indicator(
        indicator,
        source=fake_source,
        countries=("MMR",),
        year_start=2009,
        year_end=2013,
        cache_dir=tmp_path,
    )

    assert set(frame[config.COL_COUNTRY_NAME]) == {"Myanmar"}
    assert set(frame[config.COL_INDICATOR_NAME]) == {indicator.name}


def test_fetch_indicator_rejects_a_source_missing_a_column(tmp_path, indicator):
    class BrokenSource:
        def fetch(self, indicator_id, countries, year_start, year_end):
            return pd.DataFrame({config.COL_YEAR: [2011], config.COL_VALUE: [1.0]})

    with pytest.raises(ValueError, match="missing columns"):
        ingestion.fetch_indicator(
            indicator, source=BrokenSource(), cache_dir=tmp_path, year_start=2011, year_end=2011
        )


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def test_fetch_indicator_writes_cache_with_provenance(tmp_path, fake_source, indicator):
    ingestion.fetch_indicator(
        indicator,
        source=fake_source,
        countries=("MMR", "VNM"),
        year_start=2009,
        year_end=2013,
        cache_dir=tmp_path,
    )

    parquet = ingestion.cache_path(GDP, ("MMR", "VNM"), 2009, 2013, tmp_path)
    sidecar = parquet.with_suffix(".json")
    assert parquet.exists()
    assert sidecar.exists()

    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    assert metadata["indicator_id"] == GDP
    assert metadata["countries"] == ["MMR", "VNM"]
    assert metadata["source_db"] == config.WDI_SOURCE_ID
    assert metadata["row_count"] == 10


def test_second_fetch_reads_the_cache_instead_of_the_source(tmp_path, fake_source, indicator):
    kwargs = {
        "source": fake_source,
        "countries": ("MMR", "VNM"),
        "year_start": 2009,
        "year_end": 2013,
        "cache_dir": tmp_path,
    }

    first = ingestion.fetch_indicator(indicator, **kwargs)
    second = ingestion.fetch_indicator(indicator, **kwargs)

    assert fake_source.calls == [GDP]  # fetched once, served from disk after
    pd.testing.assert_frame_equal(first, second)


def test_refresh_bypasses_the_cache(tmp_path, fake_source, indicator):
    kwargs = {
        "source": fake_source,
        "countries": ("MMR", "VNM"),
        "year_start": 2009,
        "year_end": 2013,
        "cache_dir": tmp_path,
    }

    ingestion.fetch_indicator(indicator, **kwargs)
    ingestion.fetch_indicator(indicator, refresh=True, **kwargs)

    assert fake_source.calls == [GDP, GDP]


def test_cache_key_ignores_country_order_but_not_membership():
    same = ingestion.cache_key(GDP, ("VNM", "MMR"), 2000, 2024)
    reordered = ingestion.cache_key(GDP, ("MMR", "VNM"), 2000, 2024)
    different = ingestion.cache_key(GDP, ("MMR", "VNM", "KHM"), 2000, 2024)

    assert same == reordered
    assert same != different


def test_cache_key_distinguishes_year_ranges():
    assert ingestion.cache_key(GDP, ("MMR",), 2000, 2024) != ingestion.cache_key(
        GDP, ("MMR",), 2011, 2024
    )


# --------------------------------------------------------------------------- #
# Panel assembly
# --------------------------------------------------------------------------- #


def test_fetch_panel_stacks_every_indicator(tmp_path, fake_source):
    indicators = [config.INDICATORS_BY_ID[i] for i in (GDP, INTERNET, LIFE_EXPECTANCY)]

    panel = ingestion.fetch_panel(
        indicators,
        source=fake_source,
        countries=("MMR", "VNM"),
        year_start=2009,
        year_end=2013,
        cache_dir=tmp_path,
    )

    assert len(panel) == 30  # 3 indicators x 2 countries x 5 years
    assert set(panel[config.COL_INDICATOR_ID]) == {GDP, INTERNET, LIFE_EXPECTANCY}
    assert fake_source.calls == [GDP, INTERNET, LIFE_EXPECTANCY]


def test_fetch_panel_rejects_an_empty_indicator_list(tmp_path, fake_source):
    with pytest.raises(ValueError, match="No indicators"):
        ingestion.fetch_panel([], source=fake_source, cache_dir=tmp_path)


def test_fetch_panel_preserves_missing_values(tmp_path, fake_source):
    """Gaps must survive ingestion - filling happens later, and separately."""
    panel = ingestion.fetch_panel(
        [config.INDICATORS_BY_ID[INTERNET]],
        source=fake_source,
        countries=("MMR",),
        year_start=2009,
        year_end=2013,
        cache_dir=tmp_path,
    )

    assert int(panel[config.COL_VALUE].isna().sum()) == 2


# --------------------------------------------------------------------------- #
# World Bank response parsing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("raw", "expected"), [("YR2015", 2015), (2015, 2015), ("2015", 2015)])
def test_parse_year_accepts_both_world_bank_time_key_forms(raw, expected):
    assert ingestion._parse_year(raw) == expected


def test_parse_year_rejects_nonsense():
    with pytest.raises(ValueError, match="Unrecognized"):
        ingestion._parse_year("not-a-year")


def test_world_bank_source_retries_then_gives_up(monkeypatch):
    """Transport failures back off and retry, then surface a clear error."""
    monkeypatch.setattr(ingestion.time, "sleep", lambda _: None)
    source = ingestion.WorldBankSource(max_attempts=3, backoff_seconds=0)
    attempts = []

    def always_fails(*args, **kwargs):
        attempts.append(1)
        msg = "connection reset"
        raise ConnectionError(msg)

    monkeypatch.setattr(source, "_fetch_once", always_fails)

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        source.fetch(GDP, ("MMR",), 2000, 2024)

    assert len(attempts) == 3


def test_world_bank_source_succeeds_after_a_transient_failure(monkeypatch):
    monkeypatch.setattr(ingestion.time, "sleep", lambda _: None)
    source = ingestion.WorldBankSource(max_attempts=3, backoff_seconds=0)
    calls = []

    def fails_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            msg = "timeout"
            raise TimeoutError(msg)
        return [{config.COL_COUNTRY_ISO3: "MMR", config.COL_YEAR: 2011, config.COL_VALUE: 1.0}]

    monkeypatch.setattr(source, "_fetch_once", fails_once)
    frame = source.fetch(GDP, ("MMR",), 2011, 2011)

    assert len(calls) == 2
    assert frame[config.COL_VALUE].tolist() == [1.0]


def test_fake_source_satisfies_the_protocol(fake_source):
    assert isinstance(fake_source, ingestion.IndicatorSource)
    assert isinstance(FakeSource(pd.DataFrame()), ingestion.IndicatorSource)

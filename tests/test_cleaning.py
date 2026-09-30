"""Cleaning tests. Ingestion is faked, so nothing here touches the network."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from amber import cleaning, config, pipeline
from tests.conftest import GDP, INTERNET, LIFE_EXPECTANCY


def _value(frame: pd.DataFrame, iso3: str, indicator_id: str, year: int) -> float:
    """Pull a single observation out of a panel."""
    match = frame[
        (frame[config.COL_COUNTRY_ISO3] == iso3)
        & (frame[config.COL_INDICATOR_ID] == indicator_id)
        & (frame[config.COL_YEAR] == year)
    ]
    assert len(match) == 1, f"expected one row for {iso3}/{indicator_id}/{year}, got {len(match)}"
    return float(match[config.COL_VALUE].iloc[0])


# --------------------------------------------------------------------------- #
# Shape and schema
# --------------------------------------------------------------------------- #


def test_build_panel_produces_expected_shape_and_columns(raw_frame):
    panel = cleaning.build_panel(raw_frame)

    # Cleaning enriches: same rows in, same rows out, plus pillar and pre_2011.
    assert tuple(panel.columns) == config.PANEL_COLUMNS
    assert len(panel) == len(raw_frame)
    assert set(panel[config.COL_COUNTRY_ISO3]) == {"MMR", "VNM"}
    assert set(panel[config.COL_INDICATOR_ID]) == {GDP, INTERNET, LIFE_EXPECTANCY}


def test_build_panel_rejects_missing_columns(raw_frame):
    with pytest.raises(ValueError, match="missing columns"):
        cleaning.build_panel(raw_frame.drop(columns=[config.COL_VALUE]))


def test_build_panel_rejects_unconfigured_indicator(raw_frame):
    stray = raw_frame.copy()
    stray.loc[0, config.COL_INDICATOR_ID] = "XX.NOT.AN.INDICATOR"

    with pytest.raises(ValueError, match="no pillar"):
        cleaning.build_panel(stray)


# --------------------------------------------------------------------------- #
# Enrichment
# --------------------------------------------------------------------------- #


def test_each_indicator_maps_to_its_pillar(raw_frame):
    panel = cleaning.build_panel(raw_frame)
    pillars = panel.set_index(config.COL_INDICATOR_ID)[config.COL_PILLAR].to_dict()

    assert pillars[GDP] == config.Pillar.ECONOMY
    assert pillars[INTERNET] == config.Pillar.INNOVATION
    assert pillars[LIFE_EXPECTANCY] == config.Pillar.HUMAN_DEVELOPMENT


def test_pre_2011_flag_is_set_on_military_era_rows_only(raw_frame):
    panel = cleaning.build_panel(raw_frame)

    flagged_years = set(panel.loc[panel[config.COL_PRE_2011], config.COL_YEAR])
    unflagged_years = set(panel.loc[~panel[config.COL_PRE_2011], config.COL_YEAR])

    assert flagged_years == {2009, 2010}
    assert unflagged_years == {2011, 2012, 2013}
    # 6 series x 2 pre-2011 years
    assert int(panel[config.COL_PRE_2011].sum()) == 12


def test_treatment_year_is_config_not_a_column(raw_frame):
    panel = cleaning.build_panel(raw_frame)

    assert config.TREATMENT_YEAR == 2021
    assert "treatment_year" not in panel.columns


# --------------------------------------------------------------------------- #
# Missing values
# --------------------------------------------------------------------------- #


def test_raw_panel_keeps_missing_values_as_nan(raw_frame):
    panel = cleaning.build_panel(raw_frame)

    # The interior gap, the trailing gaps and the leading gap all survive.
    assert math.isnan(_value(panel, "MMR", GDP, 2011))
    assert math.isnan(_value(panel, "MMR", INTERNET, 2012))
    assert math.isnan(_value(panel, "MMR", INTERNET, 2013))
    assert math.isnan(_value(panel, "VNM", LIFE_EXPECTANCY, 2009))
    assert int(panel[config.COL_VALUE].isna().sum()) == 4


def test_interpolation_bridges_interior_gaps(raw_frame):
    filled = cleaning.interpolate_panel(cleaning.build_panel(raw_frame))

    # 1100 (2010) -> 1300 (2012) puts 2011 at 1200.
    assert _value(filled, "MMR", GDP, 2011) == pytest.approx(1200.0)


def test_interpolation_does_not_extrapolate_past_the_last_observation(raw_frame):
    filled = cleaning.interpolate_panel(cleaning.build_panel(raw_frame))

    # MMR internet stops after 2011 - a dark series must stay dark.
    assert math.isnan(_value(filled, "MMR", INTERNET, 2012))
    assert math.isnan(_value(filled, "MMR", INTERNET, 2013))


def test_interpolation_does_not_backfill_before_the_first_observation(raw_frame):
    filled = cleaning.interpolate_panel(cleaning.build_panel(raw_frame))

    assert math.isnan(_value(filled, "VNM", LIFE_EXPECTANCY, 2009))


def test_interpolation_flags_only_the_cells_it_wrote(raw_frame):
    filled = cleaning.interpolate_panel(cleaning.build_panel(raw_frame))

    imputed = filled[filled[config.COL_IMPUTED]]
    assert len(imputed) == 1
    assert imputed.iloc[0][config.COL_COUNTRY_ISO3] == "MMR"
    assert imputed.iloc[0][config.COL_YEAR] == 2011


def test_interpolation_leaves_the_source_panel_untouched(raw_frame):
    panel = cleaning.build_panel(raw_frame)
    cleaning.interpolate_panel(panel)

    assert math.isnan(_value(panel, "MMR", GDP, 2011))
    assert config.COL_IMPUTED not in panel.columns


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def test_coverage_report_counts_observations_per_series(raw_frame):
    panel = cleaning.build_panel(raw_frame)
    coverage = cleaning.build_coverage_report(panel)

    assert len(coverage) == 6  # 2 countries x 3 indicators

    internet = coverage[
        (coverage[config.COL_COUNTRY_ISO3] == "MMR")
        & (coverage[config.COL_INDICATOR_ID] == INTERNET)
    ].iloc[0]

    assert internet["n_years"] == 5
    assert internet["n_observed"] == 3
    assert internet["n_missing"] == 2
    assert internet["first_year_observed"] == 2009
    assert internet["last_year_observed"] == 2011


def test_coverage_report_flags_dark_series():
    """A series that stops reporting at the coup must be flagged, not inferred."""
    years = [2019, 2020, 2021, 2022]
    rows = [
        # Goes dark after 2020 - the Myanmar internet-users pattern.
        *[
            {
                config.COL_INDICATOR_ID: INTERNET,
                config.COL_INDICATOR_NAME: config.INDICATORS_BY_ID[INTERNET].name,
                config.COL_COUNTRY_ISO3: "MMR",
                config.COL_COUNTRY_NAME: "Myanmar",
                config.COL_YEAR: year,
                config.COL_VALUE: value,
            }
            for year, value in zip(years, [30.0, 35.0, None, None], strict=True)
        ],
        # Keeps reporting across the treatment year.
        *[
            {
                config.COL_INDICATOR_ID: INTERNET,
                config.COL_INDICATOR_NAME: config.INDICATORS_BY_ID[INTERNET].name,
                config.COL_COUNTRY_ISO3: "VNM",
                config.COL_COUNTRY_NAME: "Vietnam",
                config.COL_YEAR: year,
                config.COL_VALUE: value,
            }
            for year, value in zip(years, [68.0, 70.0, 73.0, 78.0], strict=True)
        ],
    ]

    coverage = cleaning.build_coverage_report(
        cleaning.build_panel(pd.DataFrame(rows, columns=list(config.INGESTION_COLUMNS)))
    )
    dark = coverage.set_index(config.COL_COUNTRY_ISO3)["is_dark"].to_dict()

    assert dark["MMR"] is True or bool(dark["MMR"]) is True
    assert bool(dark["VNM"]) is False


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #


def test_pipeline_writes_the_three_processed_tables(tmp_path, fake_source):
    """End to end against a fake source: no network, real file outputs."""
    indicators = tuple(config.INDICATORS_BY_ID[i] for i in (GDP, INTERNET, LIFE_EXPECTANCY))

    result = pipeline.run(
        indicators=indicators,
        countries=("MMR", "VNM"),
        year_start=2009,
        year_end=2013,
        source=fake_source,
        cache_dir=tmp_path / "raw",
        output_dir=tmp_path / "processed",
    )

    written = {path.name for path in result.written}
    assert written == {
        "panel.csv",
        "panel.parquet",
        "panel_interpolated.csv",
        "panel_interpolated.parquet",
        "coverage_report.csv",
        "coverage_report.parquet",
    }
    assert all(path.exists() for path in result.written)

    reloaded = pd.read_csv(tmp_path / "processed" / "panel.csv")
    assert tuple(reloaded.columns) == config.PANEL_COLUMNS
    assert len(reloaded) == 30  # 2 countries x 3 indicators x 5 years

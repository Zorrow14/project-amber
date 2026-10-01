"""Historical-layer tests: coverage discovery, the three rulers, reliability, divergence.

Everything runs offline against synthetic series served by the shared
``FakeSource``. Rendering is checked for completion and captions, not pixels.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from amber import config, figures, historical
from amber.config import (
    CoverageStatus,
    DivergenceComparator,
    DivergenceScenario,
    HistoricalSource,
    Reliability,
)
from amber.modeling import divergence as dv
from amber.modeling import index
from tests.conftest import FakeSource

GDP = config.GDP_PC_INDICATOR
LIFE = "SP.DYN.LE00.IN"
INTERNET = "IT.NET.USER.ZS"
MOBILE = "IT.CEL.SETS.P2"
POP = "SP.POP.TOTL"
CURRENT_USD = "NY.GDP.PCAP.CD"
YEARS = range(config.HISTORICAL_START, config.HISTORICAL_END + 1)

# Constant annual growth per country, so expected paths are closed-form.
GROWTH = {"MMR": 0.02, "THA": 0.05, "VNM": 0.03, "BGD": 0.01}
START_LEVEL = {"MMR": 100.0, "THA": 400.0, "VNM": 150.0, "BGD": 200.0}


def _rows(indicator_id: str, iso3: str, values: dict[int, float | None]) -> list[dict]:
    name = config.INDICATORS_BY_ID.get(indicator_id)
    return [
        {
            config.COL_INDICATOR_ID: indicator_id,
            config.COL_INDICATOR_NAME: name.name if name else indicator_id,
            config.COL_COUNTRY_ISO3: iso3,
            config.COL_COUNTRY_NAME: config.HISTORICAL_COUNTRIES[iso3],
            config.COL_YEAR: year,
            config.COL_VALUE: value,
        }
        for year, value in values.items()
    ]


@pytest.fixture
def long_raw() -> pd.DataFrame:
    """Ingestion-shaped long series for four countries, 1960-2024.

    * GDP and life expectancy: complete from 1960 - they extend.
    * Internet: from 2000 only - no pre-2000 data, so it must not extend.
    * Mobile: zeros 1960-1992, then values - zeros must not count.
    * Vietnam's GDP starts in 1984, as in WDI.
    * Current-US$ GDP: present in the frame, and never allowed through.
    """
    rows: list[dict] = []
    for iso3, g in GROWTH.items():
        first = 1984 if iso3 == "VNM" else config.HISTORICAL_START
        gdp = {
            y: START_LEVEL[iso3] * np.exp(g * (y - first)) if y >= first else None for y in YEARS
        }
        rows += _rows(GDP, iso3, gdp)
        rows += _rows(CURRENT_USD, iso3, {y: 9_999.0 for y in YEARS})
        rows += _rows(LIFE, iso3, {y: 45 + 0.3 * (y - 1960) for y in YEARS})
        rows += _rows(INTERNET, iso3, {y: (y - 1999) * 2.0 if y >= 2000 else None for y in YEARS})
        rows += _rows(MOBILE, iso3, {y: 0.0 if y < 1993 else float(y - 1992) for y in YEARS})
    return pd.DataFrame(rows, columns=list(config.INGESTION_COLUMNS))


CANDIDATES = {GDP: "GDP pc", LIFE: "Life expectancy", INTERNET: "Internet", MOBILE: "Mobile"}


@pytest.fixture
def coverage(long_raw: pd.DataFrame) -> pd.DataFrame:
    return historical.discover_coverage(long_raw, CANDIDATES)


@pytest.fixture
def table(long_raw: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    return historical.build_historical(long_raw, coverage)


@pytest.fixture
def full_raw(long_raw: pd.DataFrame) -> pd.DataFrame:
    """long_raw extended to every historical country (Thailand's growth for the rest)."""
    rows = [long_raw]
    for iso3 in config.HISTORICAL_COUNTRY_CODES:
        if iso3 in GROWTH:
            continue
        values = {y: 300.0 * np.exp(0.03 * (y - 1960)) for y in YEARS}
        rows.append(pd.DataFrame(_rows(GDP, iso3, values)))
    frame = pd.concat(rows, ignore_index=True)
    population = frame[frame[config.COL_INDICATOR_ID] == GDP].assign(
        **{config.COL_INDICATOR_ID: POP}
    )
    return pd.concat([frame, population], ignore_index=True)


@pytest.fixture
def full_table(full_raw: pd.DataFrame) -> pd.DataFrame:
    """The historical table over every configured country, for the donor average."""
    return historical.build_historical(full_raw, historical.discover_coverage(full_raw, CANDIDATES))


def _status(coverage: pd.DataFrame, indicator_id: str) -> str:
    return str(coverage.set_index(config.COL_INDICATOR_ID).loc[indicator_id, historical.COL_STATUS])


# --------------------------------------------------------------------------- #
# Coverage discovery
# --------------------------------------------------------------------------- #


def test_coverage_discovery_extends_series_with_real_pre_2000_data(coverage):
    assert _status(coverage, GDP) == CoverageStatus.EXTENDS
    assert _status(coverage, LIFE) == CoverageStatus.EXTENDS


def test_coverage_discovery_drops_a_series_with_no_pre_2000_data(coverage, table):
    assert _status(coverage, INTERNET) == CoverageStatus.INSUFFICIENT
    assert INTERNET not in set(table[config.COL_INDICATOR_ID])


def test_structural_zeros_do_not_count_as_coverage(coverage):
    row = coverage.set_index(config.COL_INDICATOR_ID).loc[MOBILE]
    assert row[historical.COL_STATUS] == CoverageStatus.INSUFFICIENT
    assert row[historical.COL_N_ZERO] == 1993 - config.HISTORICAL_START
    assert row[historical.COL_N_OBSERVED] == config.HISTORICAL_COVERAGE_BEFORE - 1993


def test_coverage_report_lists_ruler_exclusions_with_their_reason(coverage):
    excluded = coverage[coverage[historical.COL_STATUS] == CoverageStatus.EXCLUDED_RULER]
    assert set(excluded[config.COL_INDICATOR_ID]) == set(config.HISTORICAL_RULER_EXCLUDED)
    assert excluded[historical.COL_REASON].str.len().gt(0).all()


# --------------------------------------------------------------------------- #
# The three rulers
# --------------------------------------------------------------------------- #


def test_current_usd_is_excluded_from_the_historical_layer(long_raw, table):
    assert CURRENT_USD in set(long_raw[config.COL_INDICATOR_ID])  # it was offered...
    assert not table[config.COL_INDICATOR_ID].str.endswith(config.CURRENT_USD_SUFFIX).any()
    # ...and even marking it as extending cannot let it through.
    forced = pd.DataFrame(
        {config.COL_INDICATOR_ID: [CURRENT_USD], historical.COL_STATUS: [CoverageStatus.EXTENDS]}
    )
    assert historical.build_historical(long_raw, forced).empty


def test_current_usd_is_never_a_candidate_or_fetched():
    assert not any(i.endswith(config.CURRENT_USD_SUFFIX) for i in historical.candidate_series())
    assert not set(historical.candidate_series()) & set(config.HISTORICAL_RULER_EXCLUDED)
    with pytest.raises(ValueError, match="Ruler-excluded"):
        historical.fetch_candidates({CURRENT_USD: "GDP pc, current US$"})


def test_wdi_rows_carry_the_wb_constant_source_tag(table):
    assert set(table[config.COL_SOURCE]) == {HistoricalSource.WB_CONSTANT}
    assert list(table.columns) == list(config.HISTORICAL_COLUMNS)


@pytest.fixture
def maddison_csv(tmp_path: Path) -> Path:
    """An MPD-shaped export, with rows either side of 1960 and another country."""
    path = tmp_path / "maddison.csv"
    pd.DataFrame(
        {
            "countrycode": ["MMR"] * 5 + ["THA"],
            "country": ["Myanmar"] * 5 + ["Thailand"],
            "year": [1913, 1938, 1950, 1959, 1960, 1950],
            "gdppc": [800.0, 900.0, 700.0, 850.0, 860.0, 1500.0],
            "pop": [1.0] * 6,
        }
    ).to_csv(path, index=False)
    return path


def test_maddison_rows_carry_their_own_tag_and_never_merge(table, maddison_csv):
    maddison = historical.load_maddison(maddison_csv)
    combined = historical.combine(table, maddison)

    rows = combined[combined[config.COL_SOURCE] == HistoricalSource.MADDISON]
    assert set(rows[config.COL_INDICATOR_ID]) == {config.MADDISON_INDICATOR}
    assert set(rows[config.COL_COUNTRY_ISO3]) == {config.TREATED_COUNTRY}
    assert rows[config.COL_YEAR].max() <= config.MADDISON_LAST_YEAR  # 1960 left to WDI
    assert rows[config.COL_VALUE].tolist() == [800.0, 900.0, 700.0, 850.0]  # untouched

    # The WDI constant-US$ series holds no Maddison value and no pre-1960 year.
    wdi = combined[combined[config.COL_INDICATOR_ID] == GDP]
    assert set(wdi[config.COL_SOURCE]) == {HistoricalSource.WB_CONSTANT}
    assert wdi[config.COL_YEAR].min() == config.HISTORICAL_START
    assert combined.groupby(config.COL_INDICATOR_ID)[config.COL_SOURCE].nunique().max() == 1


def test_a_maddison_row_claiming_a_wdi_id_is_refused(table, maddison_csv):
    maddison = historical.load_maddison(maddison_csv)
    maddison[config.COL_INDICATOR_ID] = GDP
    with pytest.raises(ValueError, match="own indicator id"):
        historical.combine(table, maddison)


def test_a_missing_maddison_export_is_skipped_with_a_note(tmp_path, caplog):
    with caplog.at_level("INFO"):
        frame = historical.load_maddison(tmp_path / "absent.csv")
    assert frame.empty
    assert list(frame.columns) == list(config.HISTORICAL_COLUMNS)
    assert "No Maddison export" in caplog.text


def test_a_malformed_maddison_export_fails_clearly(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"iso": ["MMR"], "year": [1950], "gdp": [1.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="MPD columns"):
        historical.load_maddison(path)


# --------------------------------------------------------------------------- #
# Reliability
# --------------------------------------------------------------------------- #


def test_pre_1990_myanmar_rows_are_flagged_low(table):
    cutoff = config.RELIABILITY_LOW_BEFORE[config.TREATED_COUNTRY]
    mmr = table[table[config.COL_COUNTRY_ISO3] == config.TREATED_COUNTRY]
    early = mmr[config.COL_YEAR] < cutoff
    assert (mmr.loc[early, config.COL_RELIABILITY] == Reliability.LOW).all()
    assert (mmr.loc[~early, config.COL_RELIABILITY] == Reliability.STANDARD).all()


def test_other_countries_are_not_flagged_by_myanmars_rule(table):
    others = table[table[config.COL_COUNTRY_ISO3] != config.TREATED_COUNTRY]
    assert (others[config.COL_RELIABILITY] == Reliability.STANDARD).all()


def test_maddison_rows_follow_the_same_reliability_rule(maddison_csv):
    maddison = historical.load_maddison(maddison_csv)
    assert (maddison[config.COL_RELIABILITY] == Reliability.LOW).all()


# --------------------------------------------------------------------------- #
# Divergence scenario
# --------------------------------------------------------------------------- #


def test_divergence_grows_the_anchor_at_the_comparators_rate(table):
    result = historical.run_divergence(table, [config.DIVERGENCE_SCENARIOS[0]])["track_thailand"]
    path = result.path.set_index(config.COL_YEAR)
    t = np.arange(len(path))
    expected = START_LEVEL["MMR"] * np.exp(GROWTH["THA"] * t)

    np.testing.assert_allclose(path[dv.COL_PATH], expected, rtol=1e-12)
    assert result.anchor_value == pytest.approx(START_LEVEL["MMR"])
    assert path.loc[config.HISTORICAL_START, dv.COL_PATH] == pytest.approx(START_LEVEL["MMR"])
    ratio = np.exp((GROWTH["THA"] - GROWTH["MMR"]) * t)
    np.testing.assert_allclose(path[dv.COL_RATIO], ratio, rtol=1e-12)
    np.testing.assert_allclose(path[config.COL_GAP], path[dv.COL_PATH] - path[dv.COL_ACTUAL])


def test_divergence_for_one_country_is_the_anchor_times_its_cumulative_growth(table):
    result = historical.run_divergence(table, [config.DIVERGENCE_SCENARIOS[0]])["track_thailand"]
    levels = table[table[config.COL_INDICATOR_ID] == GDP].pivot(
        index=config.COL_YEAR, columns=config.COL_COUNTRY_ISO3, values=config.COL_VALUE
    )
    anchor = config.HISTORICAL_START
    closed_form = levels.loc[anchor, "MMR"] * levels["THA"] / levels.loc[anchor, "THA"]
    np.testing.assert_allclose(result.path[dv.COL_PATH], closed_form.to_numpy(), rtol=1e-12)


def test_the_regional_average_averages_the_units_observed_each_year(table):
    comparator = DivergenceComparator("Average", ("VNM", "BGD"))
    scenario = DivergenceScenario("avg", "avg", config.HISTORICAL_START)
    levels = table[table[config.COL_INDICATOR_ID] == GDP].pivot(
        index=config.COL_YEAR, columns=config.COL_COUNTRY_ISO3, values=config.COL_VALUE
    )
    result = dv.divergence_path(levels["MMR"], levels, scenario, comparator)
    path = result.path.set_index(config.COL_YEAR)

    # Bangladesh alone until Vietnam has two consecutive years (1984-85), then the mean.
    assert path.loc[1984, dv.COL_N_UNITS] == 1
    assert path.loc[1985, dv.COL_N_UNITS] == 2
    assert path.loc[1970, dv.COL_GROWTH] == pytest.approx(GROWTH["BGD"])
    assert path.loc[1990, dv.COL_GROWTH] == pytest.approx((GROWTH["BGD"] + GROWTH["VNM"]) / 2)


def test_divergence_is_flagged_illustrative_with_no_inference(full_table):
    results = historical.run_divergence(full_table)
    metrics = historical.divergence_metrics(results)
    paths = historical.divergence_table(results)

    assert all(r.illustrative for r in results.values())
    assert metrics[historical.COL_ILLUSTRATIVE].all()
    assert paths[historical.COL_ILLUSTRATIVE].all()
    banned = {"p_value", "credible", "pre_rmse", "rank"}
    assert not banned & {c.lower() for c in (*metrics.columns, *paths.columns)}
    row = metrics.set_index(config.COL_SCENARIO).loc["track_thailand"].to_dict()
    assert row["anchor_year"] == config.HISTORICAL_START
    assert row["comparator"] == "THA"
    assert row["ratio_latest"] == pytest.approx(
        np.exp((GROWTH["THA"] - GROWTH["MMR"]) * (config.HISTORICAL_END - config.HISTORICAL_START))
    )
    assert metrics["default"].sum() == 1


def test_anchor_sensitivity_reruns_every_scenario_from_each_anchor(full_table):
    table = historical.sensitivity_metrics(full_table)
    anchors = {*config.DIVERGENCE_SENSITIVITY_ANCHORS, config.HISTORICAL_START}
    for scenario in config.DIVERGENCE_SCENARIOS:
        rows = table[table[config.COL_SCENARIO] == scenario.name]
        assert set(rows["anchor_year"]) == anchors
    assert table[historical.COL_ILLUSTRATIVE].all()
    default = table[table["default"]]
    assert len(default) == 1
    assert default.iloc[0][config.COL_SCENARIO] == config.DIVERGENCE_DEFAULT_SCENARIO

    # Constant growth: from any anchor a, the 2024 ratio is exp((g_THA - g_MMR) (2024 - a)).
    thailand = table[table[config.COL_SCENARIO] == "track_thailand"]
    for anchor, ratio in zip(thailand["anchor_year"], thailand["ratio_latest"], strict=True):
        gap = (GROWTH["THA"] - GROWTH["MMR"]) * (config.HISTORICAL_END - anchor)
        assert ratio == pytest.approx(np.exp(gap))


def test_divergence_paths_carry_myanmars_reliability(full_table):
    paths = historical.divergence_table(historical.run_divergence(full_table))
    cutoff = config.RELIABILITY_LOW_BEFORE[config.TREATED_COUNTRY]
    low = paths[config.COL_YEAR] < cutoff
    assert (paths.loc[low, config.COL_RELIABILITY] == Reliability.LOW).all()
    assert (paths.loc[~low, config.COL_RELIABILITY] == Reliability.STANDARD).all()


def test_divergence_stops_rather_than_bridging_a_gap(table):
    gappy = table.copy()
    hole = (gappy[config.COL_COUNTRY_ISO3] == "THA") & (gappy[config.COL_YEAR] == 2000)
    gappy.loc[hole & (gappy[config.COL_INDICATOR_ID] == GDP), config.COL_VALUE] = np.nan
    result = historical.run_divergence(gappy, [config.DIVERGENCE_SCENARIOS[0]])["track_thailand"]
    path = result.path.set_index(config.COL_YEAR)[dv.COL_PATH]
    assert path.loc[:1999].notna().all()
    assert path.loc[2000:].isna().all()
    assert result.latest[config.COL_YEAR] == 1999


def test_an_anchor_without_a_myanmar_value_fails(table):
    empty = table[~((table[config.COL_COUNTRY_ISO3] == "MMR") & (table[config.COL_YEAR] == 1960))]
    with pytest.raises(ValueError, match="anchor year"):
        historical.run_divergence(empty, [config.DIVERGENCE_SCENARIOS[0]])


def test_divergence_ignores_maddison_rows(full_table, maddison_csv):
    with_maddison = historical.combine(full_table, historical.load_maddison(maddison_csv))
    a = historical.run_divergence(full_table)["track_thailand"].path
    b = historical.run_divergence(with_maddison)["track_thailand"].path
    pd.testing.assert_frame_equal(a, b)


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #


def test_the_shipped_historical_config_is_valid():
    config._check_historical_config()


def test_a_historical_window_inside_the_modeling_window_fails():
    with pytest.raises(ValueError, match="historical window"):
        config._check_historical_config(start=config.MODELING_WINDOW_START)


def test_an_unresolvable_comparator_fails():
    bad = {**config.DIVERGENCE_COMPARATORS, "x": DivergenceComparator("X", ("ZZZ",))}
    with pytest.raises(ValueError, match="fetched countries"):
        config._check_historical_config(comparators=bad)
    scenario = DivergenceScenario("ghost", "nowhere", config.HISTORICAL_START)
    with pytest.raises(ValueError, match="unknown comparator"):
        config._check_historical_config(scenarios=[*config.DIVERGENCE_SCENARIOS, scenario])


def test_a_divergence_anchor_out_of_range_fails():
    scenarios = [replace(config.DIVERGENCE_SCENARIOS[0], anchor_year=1950)]
    with pytest.raises(ValueError, match="anchor outside"):
        config._check_historical_config(scenarios=scenarios)
    with pytest.raises(ValueError, match="sensitivity anchors"):
        config._check_historical_config(sensitivity_anchors=(1990, config.HISTORICAL_END))


def test_the_reliability_rule_must_be_defined_and_in_range():
    with pytest.raises(ValueError, match="low-reliability rule"):
        config._check_historical_config(reliability={})
    with pytest.raises(ValueError, match="Reliability rule"):
        config._check_historical_config(reliability={config.TREATED_COUNTRY: 1900})


def test_an_unexcluded_current_usd_candidate_fails():
    with pytest.raises(ValueError, match="ruler-excluded"):
        config._check_historical_config(candidates=(GDP, "NE.EXP.GNFS.CD"))


# --------------------------------------------------------------------------- #
# End to end, and isolation from phases 1-6
# --------------------------------------------------------------------------- #


def test_run_writes_the_tables_and_figures(tmp_path, full_raw, maddison_csv):
    source = FakeSource(full_raw)
    result = historical.run(
        source=source,
        cache_dir=tmp_path / "raw",
        output_dir=tmp_path / "out",
        figures_dir=tmp_path / "fig",
        maddison_path=maddison_csv,
        panel_path=tmp_path / "no-panel.csv",
    )

    assert CURRENT_USD not in source.calls
    assert not set(source.calls) & set(config.HISTORICAL_RULER_EXCLUDED)
    for stem in (
        config.HISTORICAL_STEM,
        config.HISTORICAL_COVERAGE_STEM,
        config.HISTORICAL_DIVERGENCE_STEM,
        config.HISTORICAL_DIVERGENCE_METRICS_STEM,
        config.HISTORICAL_DIVERGENCE_SENSITIVITY_STEM,
    ):
        assert (tmp_path / "out" / f"{stem}.csv").exists()
    assert {p.name for p in result.figures} == {
        config.HISTORICAL_FIGURE_GDP,
        config.HISTORICAL_FIGURE_DIVERGENCE,
    }
    assert set(result.historical[config.COL_SOURCE]) == set(HistoricalSource)


def test_the_historical_layer_leaves_the_2011_index_unchanged(tmp_path, full_raw):
    """A historical run writes no phase 1-6 table and leaves the index as it was.

    The index is computed from a 2011+ panel before and after the run.
    """
    out = tmp_path / "out"
    rng = np.random.default_rng(3)
    panel = pd.DataFrame(
        [
            {
                config.COL_INDICATOR_ID: ind.id,
                config.COL_INDICATOR_NAME: ind.name,
                config.COL_PILLAR: str(ind.pillar),
                config.COL_COUNTRY_ISO3: iso3,
                config.COL_COUNTRY_NAME: config.COUNTRIES[iso3],
                config.COL_YEAR: year,
                config.COL_VALUE: float(rng.uniform(600, 5000))
                if ind.id in config.LOG_TRANSFORM
                else float(rng.uniform(5, 90)),
                config.COL_PRE_2011: False,
            }
            for iso3 in config.COUNTRY_CODES
            for ind in config.INDICATORS
            for year in range(config.MODELING_WINDOW_START, 2016)
        ]
    )
    before = index.compute_index(panel)

    historical.run(
        source=FakeSource(full_raw),
        cache_dir=tmp_path / "raw",
        output_dir=out,
        figures_dir=tmp_path / "fig",
        maddison_path=tmp_path / "absent.csv",
        panel_path=tmp_path / "no-panel.csv",
        render=False,
    )

    pd.testing.assert_frame_equal(index.compute_index(panel), before)
    assert before[config.COL_YEAR].min() == config.MODELING_WINDOW_START
    historical_stems = {
        config.HISTORICAL_STEM,
        config.HISTORICAL_COVERAGE_STEM,
        config.HISTORICAL_DIVERGENCE_STEM,
        config.HISTORICAL_DIVERGENCE_METRICS_STEM,
        config.HISTORICAL_DIVERGENCE_SENSITIVITY_STEM,
    }
    phase_1_to_6 = {
        config.PANEL_STEM,
        config.PANEL_INTERPOLATED_STEM,
        config.COVERAGE_REPORT_STEM,
        *config.RELEASE_STEMS,
    } - historical_stems
    written = {p.stem for p in out.iterdir()}
    assert written == historical_stems
    assert not written & phase_1_to_6


def test_the_historical_figure_draws_maddison_on_its_own_axis(table, maddison_csv):
    combined = historical.combine(table, historical.load_maddison(maddison_csv))
    without = figures.historical_gdp_figure(table)
    with_maddison = figures.historical_gdp_figure(combined)
    assert isinstance(with_maddison, Figure)
    assert len(without.axes) == 1
    assert len(with_maddison.axes) == 2
    labels = [ax.get_ylabel() for ax in with_maddison.axes]
    assert any("2011 int$" in label for label in labels)
    assert any("constant 2015 US$" in label for label in labels)


def _texts(fig: Figure) -> str:
    texts = [t.get_text() for t in fig.texts]
    for ax in fig.axes:
        texts += [t.get_text() for t in ax.texts]
        legend = ax.get_legend()
        if legend:
            texts += [t.get_text() for t in legend.get_texts()]
    return " ".join(texts)


def test_the_historical_figures_show_their_caveats(full_table):
    gdp_text = _texts(figures.historical_gdp_figure(full_table))
    assert "low reliability" in gdp_text.lower()
    assert "current-US" in gdp_text

    result = historical.run_divergence(full_table)["track_thailand"]
    assert (
        "counterfactual"
        not in _texts(figures.historical_divergence_figure(full_table, result)).lower()
    )


def test_reliability_and_the_modeling_window_are_two_separate_cues(full_table):
    fig = figures.historical_gdp_figure(full_table)
    legend = fig.axes[0].get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    reliability = [label for label in labels if "Low reliability" in label]
    window = [label for label in labels if "Modeling window" in label]
    assert len(reliability) == 1 and len(window) == 1
    assert str(config.RELIABILITY_LOW_BEFORE[config.TREATED_COUNTRY]) in reliability[0]
    assert str(config.MODELING_WINDOW_START) in window[0]
    assert "not data quality" in window[0]


def test_without_maddison_the_chart_implies_no_pre_1960_data(full_table):
    fig = figures.historical_gdp_figure(full_table)
    assert len(fig.axes) == 1
    assert fig.axes[0].get_xlim()[0] >= config.HISTORICAL_START - 1
    assert "maddison" not in _texts(fig).lower()


def test_the_divergence_figure_shows_its_caveats(full_table):
    result = historical.run_divergence(full_table)["track_thailand"]
    text = _texts(figures.historical_divergence_figure(full_table, result))
    assert "not a causal estimate" in text
    assert "Illustrative" in text
    assert "low reliability" in text.lower()
    assert "counterfactual" not in text.lower()

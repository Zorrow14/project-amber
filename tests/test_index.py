"""Development index tests. Inputs are small synthetic panels with known answers."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from amber import config
from amber.config import Pillar, Polarity
from amber.modeling import index

GDP_PC = "NY.GDP.PCAP.KD"
GDP_GROWTH = "NY.GDP.MKTP.KD.ZG"
INTERNET = "IT.NET.USER.ZS"
LIFE_EXP = "SP.DYN.LE00.IN"
U5_MORTALITY = "SH.DYN.MORT"

FLOOR = config.NORMALIZED_FLOOR


def _panel(rows: list[tuple[str, str, int, float | None]]) -> pd.DataFrame:
    """Build an interpolated-panel-shaped frame from (iso3, indicator, year, value)."""
    return pd.DataFrame(
        [
            {
                config.COL_INDICATOR_ID: indicator_id,
                config.COL_INDICATOR_NAME: config.INDICATORS_BY_ID[indicator_id].name,
                config.COL_PILLAR: str(config.PILLAR_BY_INDICATOR[indicator_id]),
                config.COL_COUNTRY_ISO3: iso3,
                config.COL_COUNTRY_NAME: config.COUNTRIES[iso3],
                config.COL_YEAR: year,
                config.COL_VALUE: np.nan if value is None else value,
                config.COL_PRE_2011: year < config.MODELING_WINDOW_START,
            }
            for iso3, indicator_id, year, value in rows
        ]
    )


def _full_panel(seed: int = 7) -> pd.DataFrame:
    """Every indicator, three countries, 2009-2015, including negative values."""
    rng = np.random.default_rng(seed)
    rows = []
    for iso3 in ("MMR", "VNM", "KHM"):
        for indicator_id in config.INDICATORS_BY_ID:
            for year in range(2009, 2016):
                if indicator_id == GDP_PC:
                    value = float(rng.uniform(800, 5000))
                elif indicator_id in {GDP_GROWTH, "BX.KLT.DINV.WD.GD.ZS"}:
                    value = float(rng.uniform(-12, 10))  # growth and FDI can go negative
                else:
                    value = float(rng.uniform(1, 100))
                rows.append((iso3, indicator_id, year, value))
    return _panel(rows)


def _score(normalized: pd.DataFrame, iso3: str, indicator_id: str, year: int) -> float:
    match = normalized[
        (normalized[config.COL_COUNTRY_ISO3] == iso3)
        & (normalized[config.COL_INDICATOR_ID] == indicator_id)
        & (normalized[config.COL_YEAR] == year)
    ]
    assert len(match) == 1
    return float(match[config.COL_NORMALIZED].iloc[0])


def _series(result: pd.DataFrame, iso3: str, series: str, year: int) -> pd.Series:
    match = result[
        (result[config.COL_COUNTRY_ISO3] == iso3)
        & (result[config.COL_SERIES] == series)
        & (result[config.COL_YEAR] == year)
    ]
    assert len(match) == 1, f"expected one {series} row for {iso3}/{year}, got {len(match)}"
    return match.iloc[0]


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def test_polarity_config_marks_poverty_and_mortality_negative():
    negative = {k for k, v in config.INDICATOR_POLARITY.items() if v == Polarity.NEGATIVE}

    assert negative == {"SI.POV.DDAY", U5_MORTALITY}
    assert set(config.INDICATOR_POLARITY) == set(config.INDICATORS_BY_ID)


def test_log_transform_config_is_income_only():
    assert frozenset({GDP_PC}) == config.LOG_TRANSFORM


def test_default_weights_are_equal_thirds():
    assert config.DEFAULT_PILLAR_WEIGHTS == {p: pytest.approx(1 / 3) for p in Pillar}


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


def test_negative_polarity_inverts_the_score():
    # Under-5 mortality: VNM's low value is the good outcome.
    normalized = index.normalize_indicators(
        _panel([("MMR", U5_MORTALITY, 2015, 80.0), ("VNM", U5_MORTALITY, 2015, 20.0)])
    )

    assert _score(normalized, "VNM", U5_MORTALITY, 2015) == pytest.approx(1.0)
    assert _score(normalized, "MMR", U5_MORTALITY, 2015) == pytest.approx(FLOOR)


def test_positive_polarity_keeps_the_direction():
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, 60.0), ("VNM", LIFE_EXP, 2015, 75.0)])
    )

    assert _score(normalized, "VNM", LIFE_EXP, 2015) == pytest.approx(1.0)
    assert _score(normalized, "MMR", LIFE_EXP, 2015) == pytest.approx(FLOOR)


def test_income_is_logged_before_min_max():
    # 100 -> 1,000 -> 10,000: evenly spaced in log, lopsided in levels.
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", GDP_PC, 2015, 100.0),
                ("VNM", GDP_PC, 2015, 1_000.0),
                ("KHM", GDP_PC, 2015, 10_000.0),
            ]
        )
    )

    middle = _score(normalized, "VNM", GDP_PC, 2015)
    assert middle == pytest.approx(0.5)  # log scale
    assert middle != pytest.approx(900 / 9_900)  # what linear min-max would give


def test_non_income_indicators_are_not_logged():
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2015, 60.0),
                ("VNM", LIFE_EXP, 2015, 65.0),
                ("KHM", LIFE_EXP, 2015, 80.0),
            ]
        )
    )

    assert _score(normalized, "VNM", LIFE_EXP, 2015) == pytest.approx(0.25)


def test_bounds_are_pooled_across_countries_and_years():
    # The max is set by VNM in 2016, so MMR 2015 is scored against it.
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2015, 60.0),
                ("MMR", LIFE_EXP, 2016, 70.0),
                ("VNM", LIFE_EXP, 2015, 65.0),
                ("VNM", LIFE_EXP, 2016, 80.0),
            ]
        )
    )

    assert _score(normalized, "MMR", LIFE_EXP, 2016) == pytest.approx(0.5)


def test_pre_2011_rows_are_excluded_and_do_not_set_bounds():
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2009, 10.0),  # military-era outlier
                ("MMR", LIFE_EXP, 2015, 60.0),
                ("VNM", LIFE_EXP, 2015, 70.0),
                ("KHM", LIFE_EXP, 2015, 80.0),
            ]
        )
    )

    assert set(normalized[config.COL_YEAR]) == {2015}
    assert _score(normalized, "VNM", LIFE_EXP, 2015) == pytest.approx(0.5)


def test_clipping_lifts_the_pool_minimum_off_zero():
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, 60.0), ("VNM", LIFE_EXP, 2015, 75.0)])
    )

    assert normalized[config.COL_NORMALIZED].min() == pytest.approx(FLOOR)
    assert (normalized[config.COL_NORMALIZED] > 0).all()


def test_log_transform_rejects_non_positive_income():
    with pytest.raises(ValueError, match="non-positive"):
        index.normalize_indicators(
            _panel([("MMR", GDP_PC, 2015, 0.0), ("VNM", GDP_PC, 2015, 1_000.0)])
        )


def test_missing_values_are_not_scored():
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2015, None),
                ("VNM", LIFE_EXP, 2015, 70.0),
                ("KHM", LIFE_EXP, 2015, 65.0),
            ]
        )
    )

    assert set(normalized[config.COL_COUNTRY_ISO3]) == {"VNM", "KHM"}


def test_an_indicator_with_no_spread_is_dropped_not_scored():
    # One observation means min == max: no information, so no score.
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, None), ("VNM", LIFE_EXP, 2015, 70.0)])
    )

    assert normalized.empty


# --------------------------------------------------------------------------- #
# Geometric mean and weights
# --------------------------------------------------------------------------- #


def test_geometric_mean_matches_hand_computed_value():
    # (0.2 * 0.4 * 0.8) ** (1/3) = 0.064 ** (1/3) = 0.4
    assert index.weighted_geometric_mean([0.2, 0.4, 0.8]) == pytest.approx(0.4)
    assert index.weighted_geometric_mean([0.25, 1.0]) == pytest.approx(0.5)


def test_weighted_geometric_mean_matches_hand_computed_value():
    values = [0.2, 0.4, 0.8]
    expected = math.exp(0.5 * math.log(0.2) + 0.25 * math.log(0.4) + 0.25 * math.log(0.8))

    assert index.weighted_geometric_mean(values, [0.5, 0.25, 0.25]) == pytest.approx(expected)


def test_weights_that_do_not_sum_to_one_are_renormalized():
    values = [0.2, 0.4, 0.8]

    assert index.weighted_geometric_mean(values, [2, 1, 1]) == pytest.approx(
        index.weighted_geometric_mean(values, [0.5, 0.25, 0.25])
    )


def test_equal_weights_reproduce_the_simple_geometric_mean():
    values = [0.2, 0.4, 0.8]

    assert index.weighted_geometric_mean(values, [7, 7, 7]) == pytest.approx(
        index.weighted_geometric_mean(values)
    )


def test_resolve_weights_renormalizes_any_scale():
    resolved = index.resolve_weights({"economy": 2, "innovation": 1, "human_development": 1})

    assert resolved == {
        Pillar.ECONOMY: pytest.approx(0.5),
        Pillar.INNOVATION: pytest.approx(0.25),
        Pillar.HUMAN_DEVELOPMENT: pytest.approx(0.25),
    }


@pytest.mark.parametrize(
    ("weights", "match"),
    [
        ({"economy": 1, "innovation": 1}, "every pillar"),
        ({"economy": 1, "innovation": 1, "human_development": -1}, "non-negative"),
        ({"economy": 0, "innovation": 0, "human_development": 0}, "positive"),
        ({"economy": 1, "innovation": 1, "human_development": 1, "vibes": 1}, "Unknown"),
        ({"economy": float("nan"), "innovation": 1, "human_development": 1}, "finite"),
    ],
)
def test_resolve_weights_rejects_invalid_input(weights, match):
    with pytest.raises(ValueError, match=match):
        index.resolve_weights(weights)


@pytest.mark.parametrize(("values", "weights"), [([], None), ([0.5, 0.0], None), ([0.5], [1, 2])])
def test_geometric_mean_rejects_invalid_input(values, weights):
    with pytest.raises(ValueError):
        index.weighted_geometric_mean(values, weights)


# --------------------------------------------------------------------------- #
# Pillars
# --------------------------------------------------------------------------- #


def test_pillar_is_the_geometric_mean_of_its_indicators():
    panel = _full_panel()
    normalized = index.normalize_indicators(panel)
    result = index.compute_index(panel)

    scores = normalized[
        (normalized[config.COL_COUNTRY_ISO3] == "MMR")
        & (normalized[config.COL_YEAR] == 2013)
        & (normalized[config.COL_PILLAR] == Pillar.ECONOMY)
    ][config.COL_NORMALIZED].tolist()

    assert len(scores) == 4
    assert _series(result, "MMR", "economy", 2013)[config.COL_VALUE] == pytest.approx(
        index.weighted_geometric_mean(scores)
    )


def test_missing_indicator_is_skipped_not_scored_as_zero():
    # Economy pillar: MMR is missing GDP growth in 2015, VNM and KHM are not.
    panel = _panel(
        [
            ("MMR", GDP_PC, 2015, 1_000.0),
            ("VNM", GDP_PC, 2015, 3_000.0),
            ("KHM", GDP_PC, 2015, 1_500.0),
            ("MMR", GDP_GROWTH, 2015, None),
            ("VNM", GDP_GROWTH, 2015, 7.0),
            ("KHM", GDP_GROWTH, 2015, 5.0),
        ]
    )
    normalized = index.normalize_indicators(panel)
    result = index.compute_index(panel)

    mmr = _series(result, "MMR", "economy", 2015)
    khm = _series(result, "KHM", "economy", 2015)

    # Computed over the one indicator MMR has - not dragged down by a phantom 0.
    assert mmr[config.COL_VALUE] == pytest.approx(_score(normalized, "MMR", GDP_PC, 2015))
    assert mmr[config.COL_VALUE] > FLOOR
    # Coverage flags the gap: 1 of 4 economy indicators, against KHM's 2 of 4.
    assert mmr[config.COL_COVERAGE] == pytest.approx(1 / 4)
    assert khm[config.COL_COVERAGE] == pytest.approx(2 / 4)


def test_clipping_keeps_a_worst_case_pillar_above_zero():
    # MMR is the pool minimum on its only human-development indicator.
    panel = _panel([("MMR", LIFE_EXP, 2015, 50.0), ("VNM", LIFE_EXP, 2015, 75.0)])

    pillar = _series(index.compute_index(panel), "MMR", "human_development", 2015)

    assert pillar[config.COL_VALUE] == pytest.approx(FLOOR)
    assert pillar[config.COL_VALUE] > 0


# --------------------------------------------------------------------------- #
# Combined
# --------------------------------------------------------------------------- #


def test_combined_is_the_weighted_geometric_mean_of_pillars():
    panel = _full_panel()
    weights = {"economy": 2, "innovation": 1, "human_development": 1}
    result = index.compute_index(panel, weights)

    pillars = [_series(result, "VNM", str(p), 2014)[config.COL_VALUE] for p in Pillar]
    expected = index.weighted_geometric_mean(pillars, [2, 1, 1])

    assert _series(result, "VNM", "combined", 2014)[config.COL_VALUE] == pytest.approx(expected)


def test_scaled_equal_weights_match_the_default():
    panel = _full_panel()
    default = index.compute_index(panel)
    scaled = index.compute_index(panel, {"economy": 5, "innovation": 5, "human_development": 5})

    pd.testing.assert_frame_equal(default, scaled)


def test_unequal_weights_change_the_combined_score():
    panel = _full_panel()
    equal = _series(index.compute_index(panel), "KHM", "combined", 2012)[config.COL_VALUE]
    tilted = _series(
        index.compute_index(panel, {"economy": 10, "innovation": 1, "human_development": 1}),
        "KHM",
        "combined",
        2012,
    )[config.COL_VALUE]

    assert equal != pytest.approx(tilted)


def test_combined_needs_every_weighted_pillar():
    # MMR has no innovation indicator at all in 2015.
    panel = _panel(
        [
            ("MMR", GDP_PC, 2015, 1_000.0),
            ("VNM", GDP_PC, 2015, 3_000.0),
            ("MMR", LIFE_EXP, 2015, 65.0),
            ("VNM", LIFE_EXP, 2015, 74.0),
            ("VNM", INTERNET, 2015, 50.0),
            ("KHM", INTERNET, 2015, 20.0),
        ]
    )

    result = index.compute_index(panel)
    combined = result[result[config.COL_SERIES] == config.COMBINED_SERIES]
    assert "MMR" not in set(combined[config.COL_COUNTRY_ISO3])
    assert "VNM" in set(combined[config.COL_COUNTRY_ISO3])

    # Weighting innovation to zero means its absence no longer matters.
    no_innovation = index.compute_index(
        panel, {"economy": 1, "innovation": 0, "human_development": 1}
    )
    combined = no_innovation[no_innovation[config.COL_SERIES] == config.COMBINED_SERIES]
    assert "MMR" in set(combined[config.COL_COUNTRY_ISO3])


def test_combined_coverage_counts_every_indicator():
    result = index.compute_index(_full_panel())
    combined = result[result[config.COL_SERIES] == config.COMBINED_SERIES]

    assert (combined[config.COL_COVERAGE] == 1.0).all()


# --------------------------------------------------------------------------- #
# Output contract
# --------------------------------------------------------------------------- #


def test_output_schema_and_series():
    result = index.compute_index(_full_panel())

    assert tuple(result.columns) == config.INDEX_COLUMNS
    assert set(result[config.COL_SERIES]) == set(config.INDEX_SERIES)
    assert result[config.COL_YEAR].min() == config.MODELING_WINDOW_START
    # 3 countries x 5 window years x (3 pillars + combined)
    assert len(result) == 3 * 5 * 4


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_every_index_value_lies_between_floor_and_one(seed):
    result = index.compute_index(_full_panel(seed))

    assert result[config.COL_VALUE].notna().all()
    assert (result[config.COL_VALUE] >= FLOOR).all()
    assert (result[config.COL_VALUE] <= 1.0).all()
    assert (result[config.COL_COVERAGE] > 0).all()
    assert (result[config.COL_COVERAGE] <= 1.0).all()


def test_compute_index_rejects_a_panel_without_the_pre_2011_flag():
    panel = _full_panel().drop(columns=[config.COL_PRE_2011])

    with pytest.raises(ValueError, match="missing columns"):
        index.compute_index(panel)

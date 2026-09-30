"""Development index tests. Inputs are small synthetic panels with known answers."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from amber import config
from amber.config import Normalization, Pillar, Polarity
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
# Goalposts config
# --------------------------------------------------------------------------- #


def test_every_indicator_has_a_goalpost_with_a_source():
    assert set(config.GOALPOSTS) == set(config.INDICATORS_BY_ID)
    for goalpost in config.GOALPOSTS.values():
        assert goalpost.low < goalpost.high
        assert goalpost.source.strip()


def test_standard_goalposts_match_their_published_values():
    assert (config.GOALPOSTS[LIFE_EXP].low, config.GOALPOSTS[LIFE_EXP].high) == (20.0, 85.0)
    mortality = config.GOALPOSTS[U5_MORTALITY]
    assert (mortality.low, mortality.high) == (2.6, 130.0)


def test_goalposts_are_the_default_normalization():
    assert config.DEFAULT_NORMALIZATION is Normalization.GOALPOSTS


def _goal(indicator_id: str) -> tuple[float, float]:
    goalpost = config.GOALPOSTS[indicator_id]
    return goalpost.low, goalpost.high


# --------------------------------------------------------------------------- #
# Normalization - goalposts (default)
# --------------------------------------------------------------------------- #


def test_goalposts_score_against_the_fixed_bounds():
    low, high = _goal(LIFE_EXP)  # 20-85
    normalized = index.normalize_indicators(_panel([("MMR", LIFE_EXP, 2015, 72.0)]))

    assert _score(normalized, "MMR", LIFE_EXP, 2015) == pytest.approx((72 - low) / (high - low))


def test_negative_polarity_inverts_the_score():
    # Under-5 mortality: VNM's low value is the good outcome.
    low, high = _goal(U5_MORTALITY)
    normalized = index.normalize_indicators(
        _panel([("MMR", U5_MORTALITY, 2015, 80.0), ("VNM", U5_MORTALITY, 2015, 20.0)])
    )

    vnm = _score(normalized, "VNM", U5_MORTALITY, 2015)
    mmr = _score(normalized, "MMR", U5_MORTALITY, 2015)
    assert vnm > mmr
    assert vnm == pytest.approx((high - 20) / (high - low))
    assert mmr == pytest.approx((high - 80) / (high - low))


def test_positive_polarity_keeps_the_direction():
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, 60.0), ("VNM", LIFE_EXP, 2015, 75.0)])
    )

    assert _score(normalized, "VNM", LIFE_EXP, 2015) > _score(normalized, "MMR", LIFE_EXP, 2015)


def test_income_is_logged_before_scaling():
    # The geometric midpoint of the goalposts sits at 0.5 only on a log scale.
    low, high = _goal(GDP_PC)
    midpoint = math.sqrt(low * high)
    normalized = index.normalize_indicators(_panel([("MMR", GDP_PC, 2015, midpoint)]))

    score = _score(normalized, "MMR", GDP_PC, 2015)
    assert score == pytest.approx(0.5)
    assert score != pytest.approx((midpoint - low) / (high - low))  # what linear would give


def test_non_income_indicators_are_not_logged():
    low, high = _goal(LIFE_EXP)
    normalized = index.normalize_indicators(_panel([("MMR", LIFE_EXP, 2015, (low + high) / 2)]))

    assert _score(normalized, "MMR", LIFE_EXP, 2015) == pytest.approx(0.5)


def test_goalpost_scores_do_not_move_when_the_panel_grows():
    """The point of fixed goalposts: new countries or vintages cannot rewrite history."""
    small = _panel([("MMR", LIFE_EXP, 2015, 60.0), ("VNM", LIFE_EXP, 2015, 70.0)])
    grown = _panel(
        [
            ("MMR", LIFE_EXP, 2015, 60.0),
            ("VNM", LIFE_EXP, 2015, 70.0),
            ("KHM", LIFE_EXP, 2015, 80.0),  # a new, higher country
            ("VNM", LIFE_EXP, 2016, 72.0),  # a new data year
        ]
    )

    for iso3 in ("MMR", "VNM"):
        before = _score(index.normalize_indicators(small), iso3, LIFE_EXP, 2015)
        after = _score(index.normalize_indicators(grown), iso3, LIFE_EXP, 2015)
        assert before == pytest.approx(after)


def test_pooled_scores_do_move_when_the_panel_grows():
    """The contrast that motivated goalposts."""
    small = _panel([("MMR", LIFE_EXP, 2015, 60.0), ("VNM", LIFE_EXP, 2015, 70.0)])
    grown = _panel(
        [
            ("MMR", LIFE_EXP, 2015, 60.0),
            ("VNM", LIFE_EXP, 2015, 70.0),
            ("KHM", LIFE_EXP, 2015, 80.0),
        ]
    )

    before = _score(index.normalize_indicators(small, "pooled"), "VNM", LIFE_EXP, 2015)
    after = _score(index.normalize_indicators(grown, "pooled"), "VNM", LIFE_EXP, 2015)
    assert before == pytest.approx(1.0)
    assert after == pytest.approx(0.5)


def test_a_value_beyond_history_stays_on_the_same_ruler():
    # A counterfactual above anything observed still scores below 1, not squashed.
    low, high = _goal(LIFE_EXP)
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, 66.0), ("MMR", LIFE_EXP, 2016, 78.0)])
    )

    score = _score(normalized, "MMR", LIFE_EXP, 2016)
    assert score == pytest.approx((78 - low) / (high - low))
    assert score < 1.0


def test_values_outside_goalposts_clip_and_warn(caplog):
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, 15.0), ("VNM", LIFE_EXP, 2015, 90.0)])
    )

    assert _score(normalized, "MMR", LIFE_EXP, 2015) == pytest.approx(FLOOR)
    assert _score(normalized, "VNM", LIFE_EXP, 2015) == pytest.approx(1.0)
    assert "outside their goalposts" in caplog.text


def test_the_worst_goalpost_scores_the_floor_not_zero():
    _, high = _goal(U5_MORTALITY)
    normalized = index.normalize_indicators(_panel([("MMR", U5_MORTALITY, 2015, high)]))

    assert _score(normalized, "MMR", U5_MORTALITY, 2015) == pytest.approx(FLOOR)


def test_goalposts_score_a_lone_observation():
    # Unlike pooled min-max, one observation is enough - the ruler is fixed.
    normalized = index.normalize_indicators(_panel([("VNM", LIFE_EXP, 2015, 70.0)]))

    assert len(normalized) == 1


def test_pre_2011_rows_are_excluded():
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2009, 50.0), ("MMR", LIFE_EXP, 2015, 60.0)])
    )

    assert set(normalized[config.COL_YEAR]) == {2015}


def test_log_transform_rejects_non_positive_income():
    with pytest.raises(ValueError, match="non-positive"):
        index.normalize_indicators(
            _panel([("MMR", GDP_PC, 2015, 0.0), ("VNM", GDP_PC, 2015, 1_000.0)])
        )


def test_missing_values_are_not_scored():
    normalized = index.normalize_indicators(
        _panel([("MMR", LIFE_EXP, 2015, None), ("VNM", LIFE_EXP, 2015, 70.0)])
    )

    assert set(normalized[config.COL_COUNTRY_ISO3]) == {"VNM"}


def test_unknown_normalization_method_is_rejected():
    with pytest.raises(ValueError, match="vibes"):
        index.normalize_indicators(_panel([("VNM", LIFE_EXP, 2015, 70.0)]), "vibes")


# --------------------------------------------------------------------------- #
# Normalization - pooled (comparison path)
# --------------------------------------------------------------------------- #


def test_pooled_polarity_and_bounds():
    normalized = index.normalize_indicators(
        _panel([("MMR", U5_MORTALITY, 2015, 80.0), ("VNM", U5_MORTALITY, 2015, 20.0)]),
        "pooled",
    )

    assert _score(normalized, "VNM", U5_MORTALITY, 2015) == pytest.approx(1.0)
    assert _score(normalized, "MMR", U5_MORTALITY, 2015) == pytest.approx(FLOOR)


def test_pooled_income_is_logged_before_min_max():
    # 100 -> 1,000 -> 10,000: evenly spaced in log, lopsided in levels.
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", GDP_PC, 2015, 100.0),
                ("VNM", GDP_PC, 2015, 1_000.0),
                ("KHM", GDP_PC, 2015, 10_000.0),
            ]
        ),
        "pooled",
    )

    assert _score(normalized, "VNM", GDP_PC, 2015) == pytest.approx(0.5)


def test_pooled_bounds_span_countries_and_years():
    # The max is set by VNM in 2016, so MMR 2016 is scored against it.
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2015, 60.0),
                ("MMR", LIFE_EXP, 2016, 70.0),
                ("VNM", LIFE_EXP, 2015, 65.0),
                ("VNM", LIFE_EXP, 2016, 80.0),
            ]
        ),
        "pooled",
    )

    assert _score(normalized, "MMR", LIFE_EXP, 2016) == pytest.approx(0.5)


def test_pooled_pre_2011_rows_do_not_set_bounds():
    normalized = index.normalize_indicators(
        _panel(
            [
                ("MMR", LIFE_EXP, 2009, 10.0),  # military-era outlier
                ("MMR", LIFE_EXP, 2015, 60.0),
                ("VNM", LIFE_EXP, 2015, 70.0),
                ("KHM", LIFE_EXP, 2015, 80.0),
            ]
        ),
        "pooled",
    )

    assert _score(normalized, "VNM", LIFE_EXP, 2015) == pytest.approx(0.5)


def test_pooled_drops_an_indicator_with_no_spread():
    # One observation means min == max: no information, so no score.
    normalized = index.normalize_indicators(_panel([("VNM", LIFE_EXP, 2015, 70.0)]), "pooled")

    assert normalized.empty


def test_a_dropped_indicator_counts_as_absent_in_coverage():
    # Pooled: life expectancy has no spread and is dropped; mortality survives.
    panel = _panel(
        [
            ("MMR", LIFE_EXP, 2015, 70.0),
            ("VNM", LIFE_EXP, 2015, 70.0),
            ("MMR", U5_MORTALITY, 2015, 40.0),
            ("VNM", U5_MORTALITY, 2015, 20.0),
        ]
    )
    result = index.compute_index(panel, method="pooled")

    pillar = _series(result, "MMR", "human_development", 2015)
    assert pillar[config.COL_COVERAGE] == pytest.approx(1 / 4)


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #


def test_seed_goalpost_pads_by_a_share_of_the_span():
    assert index.seed_goalpost([10.0, 20.0], padding=0.25) == pytest.approx((7.5, 22.5))


def test_seed_goalpost_widens_ranges_that_cross_zero():
    # Value-based padding would narrow -12 toward zero; span-based widens it.
    assert index.seed_goalpost([-12.0, 8.0], padding=0.25) == pytest.approx((-17.0, 13.0))


def test_seed_goalpost_clamps_to_the_natural_domain():
    seeded = index.seed_goalpost([2.0, 90.0], padding=0.25, domain=(0, 100))
    assert seeded == pytest.approx((0.0, 100.0))


def test_seed_goalpost_pads_in_log_space():
    # ln-span of 100..10,000 is two decades; a quarter is half a decade each side.
    low, high = index.seed_goalpost([100.0, 10_000.0], padding=0.25, log=True)
    assert low == pytest.approx(10**1.5)
    assert high == pytest.approx(10**4.5)


def test_seed_goalpost_ignores_missing_values_and_rejects_empty_input():
    assert index.seed_goalpost([1.0, float("nan"), 3.0], padding=0) == pytest.approx((1.0, 3.0))
    with pytest.raises(ValueError, match="no observations"):
        index.seed_goalpost([float("nan")])


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

    assert len(scores) == 3  # poverty is in the panel but not the index
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
    # Coverage flags the gap: 1 of 3 economy indicators, against KHM's 2 of 3.
    assert mmr[config.COL_COVERAGE] == pytest.approx(1 / 3)
    assert khm[config.COL_COVERAGE] == pytest.approx(2 / 3)


def test_clipping_keeps_a_worst_case_pillar_above_zero():
    # MMR sits below the low goalpost on its only human-development indicator.
    panel = _panel([("MMR", LIFE_EXP, 2015, 15.0), ("VNM", LIFE_EXP, 2015, 75.0)])

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


def test_zero_weighted_pillar_does_not_drag_coverage_down():
    # MMR 2013 has no innovation data; weight innovation to zero.
    panel = _full_panel()
    innovation = panel[config.COL_PILLAR] == Pillar.INNOVATION
    gap = (panel[config.COL_COUNTRY_ISO3] == "MMR") & (panel[config.COL_YEAR] == 2013)
    panel = panel[~(innovation & gap)]

    result = index.compute_index(panel, {"economy": 1, "innovation": 0, "human_development": 1})

    # 8 of the 8 indicators in weighted pillars - not 8 of all 11.
    assert _series(result, "MMR", "combined", 2013)[config.COL_COVERAGE] == pytest.approx(1.0)


def test_combined_coverage_denominator_follows_the_weighted_pillars():
    # One economy indicator missing: 2 of 3 economy + 4 of 4 HD = 6 of 7.
    panel = _full_panel()
    drop = (
        (panel[config.COL_COUNTRY_ISO3] == "MMR")
        & (panel[config.COL_YEAR] == 2013)
        & (panel[config.COL_INDICATOR_ID] == GDP_GROWTH)
    )
    panel = panel[~drop]
    no_innovation = {"economy": 1, "innovation": 0, "human_development": 1}

    weighted = index.compute_index(panel, no_innovation)
    default = index.compute_index(panel)

    assert _series(weighted, "MMR", "combined", 2013)[config.COL_COVERAGE] == pytest.approx(6 / 7)
    assert _series(default, "MMR", "combined", 2013)[config.COL_COVERAGE] == pytest.approx(8 / 9)


def test_excluded_indicators_stay_out_of_the_index_and_its_coverage():
    panel = _full_panel()
    excluded = set(config.INDEX_EXCLUDED)

    normalized = index.normalize_indicators(panel)
    result = index.compute_index(panel)

    assert excluded <= set(panel[config.COL_INDICATOR_ID])
    assert not excluded & set(normalized[config.COL_INDICATOR_ID])
    # Every index indicator is observed, so coverage is complete without them.
    assert (result[config.COL_COVERAGE] == 1.0).all()
    # Changing an excluded series cannot move the index.
    bumped = panel.copy()
    bumped.loc[bumped[config.COL_INDICATOR_ID].isin(excluded), config.COL_VALUE] *= 0.5
    pd.testing.assert_frame_equal(index.compute_index(bumped), result)


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

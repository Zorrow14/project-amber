"""Synthetic-control tests. Offline, synthetic and seeded: every answer is known.

The core construction: six donors with distinct random paths, and a treated unit
built as an exact convex combination of three of them. SCM should recover that
combination, a zero pre-fit, and any effect injected after treatment.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from amber import config, counterfactual
from amber.modeling import synthetic_control as sc

TREATED = "MMR"
DONORS = ("VNM", "KHM", "BGD", "LAO", "NPL", "IDN")
YEARS = range(2011, 2025)
TRUE_WEIGHTS = {"VNM": 0.5, "KHM": 0.3, "BGD": 0.2}

# Few restarts keep the suite fast; the problem is a convex QP, so one good
# start suffices - restarts only guard against solver stalls.
SETTINGS = sc.SCSettings(
    treatment_year=2021, pre_start=2011, pre_end=2020, n_restarts=4, seed=7, min_donors=3
)


def _donor_paths(seed: int = 3) -> pd.DataFrame:
    """Six distinct, trending, noisy donor paths (years x donors)."""
    rng = np.random.default_rng(seed)
    t = np.arange(len(YEARS))
    paths = {
        donor: 1_000 + 400 * i + rng.uniform(20, 90) * t + rng.normal(0, 25, len(t)).cumsum()
        for i, donor in enumerate(DONORS)
    }
    return pd.DataFrame(paths, index=pd.Index(YEARS, name=config.COL_YEAR))


def _matrix(effect: float = 0.0, weights: dict[str, float] = TRUE_WEIGHTS) -> pd.DataFrame:
    """Donors plus a treated unit that is an exact combination, plus ``effect`` from 2021."""
    donors = _donor_paths()
    treated = sum(donors[d] * w for d, w in weights.items())
    treated = treated + np.where(donors.index >= 2021, effect, 0.0)
    return pd.concat([treated.rename(TREATED), donors], axis=1)


def _fit(matrix: pd.DataFrame, **kwargs: object) -> sc.SyntheticControlResult:
    params = {"treated": TREATED, "donors": DONORS, "settings": SETTINGS, "name": "y"}
    params.update(kwargs)
    return sc.fit_synthetic_control(matrix, **params)


# --------------------------------------------------------------------------- #
# Recovery
# --------------------------------------------------------------------------- #


def test_recovers_a_known_convex_combination():
    result = _fit(_matrix())

    for donor in DONORS:
        assert result.weights[donor] == pytest.approx(TRUE_WEIGHTS.get(donor, 0.0), abs=1e-3)
    assert result.pre_rmse == pytest.approx(0.0, abs=1e-3)


def test_weights_satisfy_the_simplex():
    result = _fit(_matrix())

    assert all(w >= 0 for w in result.weights.values())
    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_recovers_an_injected_post_treatment_effect():
    result = _fit(_matrix(effect=-150.0))

    post = result.gap.loc[result.gap.index >= 2021]
    pre = result.gap.loc[result.gap.index < 2021]
    assert post.to_numpy() == pytest.approx(np.full(len(post), -150.0), abs=0.5)
    assert pre.abs().max() == pytest.approx(0.0, abs=1e-2)
    assert result.post_rmse == pytest.approx(150.0, abs=0.5)


def test_gap_is_actual_minus_synthetic():
    result = _fit(_matrix(effect=-40.0))

    pd.testing.assert_series_equal(
        result.gap, (result.actual - result.synthetic).rename("gap"), check_names=True
    )


@pytest.mark.parametrize("seed", range(6))
def test_weights_stay_on_the_simplex_for_arbitrary_inputs(seed):
    # A treated path outside the donor hull: the fit is poor but still convex.
    rng = np.random.default_rng(seed)
    matrix = _matrix()
    matrix[TREATED] = rng.uniform(500, 6_000, len(matrix))

    result = _fit(matrix)

    weights = np.array(list(result.weights.values()))
    assert (weights >= 0).all()
    assert weights.sum() == pytest.approx(1.0, abs=1e-9)


def test_fits_are_deterministic_for_a_seed():
    matrix = _matrix()
    matrix[TREATED] += np.linspace(-80, 80, len(matrix))  # not exactly representable

    assert _fit(matrix).weights == _fit(matrix).weights


def test_effective_number_of_donors():
    result = _fit(_matrix())

    assert result.n_effective_donors == pytest.approx(1 / (0.5**2 + 0.3**2 + 0.2**2), rel=1e-2)
    assert set(result.positive_donors()) == set(TRUE_WEIGHTS)


def test_rmse_ratio_is_infinite_for_a_perfect_pre_fit():
    result = _fit(_matrix(effect=-100.0))

    assert result.pre_rmse < 1e-3
    assert result.rmse_ratio > 1e4 or math.isinf(result.rmse_ratio)


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #


def test_in_space_placebo_p_value_is_in_range_and_counts_every_unit():
    matrix = _matrix(effect=-150.0)
    placebos = sc.run_placebo_space(matrix, _fit(matrix))

    assert set(placebos.placebos) == set(DONORS)
    assert len(placebos.ratios) == len(DONORS) + 1
    assert 0 < placebos.p_value <= 1


def test_a_large_real_effect_hits_the_p_value_floor():
    # Perfect pre-fit plus a big break: no placebo can out-rank the treated unit.
    matrix = _matrix(effect=-400.0)
    placebos = sc.run_placebo_space(matrix, _fit(matrix))

    assert placebos.p_value == pytest.approx(1 / (len(DONORS) + 1))


def test_placebos_never_use_the_treated_unit_as_a_donor():
    matrix = _matrix(effect=-400.0)
    placebos = sc.run_placebo_space(matrix, _fit(matrix))

    for fit in placebos.placebos.values():
        assert TREATED not in fit.weights


def test_in_time_placebo_shows_no_gap_without_an_effect():
    matrix = _matrix()  # no effect at all
    fake = sc.run_placebo_time(matrix, _fit(matrix), placebo_year=2017)

    assert fake.settings.treatment_year == 2017
    assert fake.settings.pre_end == 2016
    assert fake.gap.index.max() < 2021  # real post-period data discarded
    assert fake.gap.loc[2017:2020].abs().max() == pytest.approx(0.0, abs=1e-2)


def test_in_time_placebo_rejects_a_year_with_too_little_history():
    matrix = _matrix()
    with pytest.raises(ValueError, match="Placebo year"):
        sc.run_placebo_time(matrix, _fit(matrix), placebo_year=2012)


def test_leave_one_out_refits_once_per_positively_weighted_donor():
    matrix = _matrix(effect=-100.0)
    base = _fit(matrix)
    refits = sc.leave_one_out(matrix, base)

    assert set(refits) == set(base.positive_donors()) == set(TRUE_WEIGHTS)
    for dropped, refit in refits.items():
        assert dropped not in refit.weights
    assert sc.loo_max_deviation(base, refits) > 0


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #


def test_donor_missing_data_in_the_fit_window_is_dropped_with_a_warning(caplog):
    matrix = _matrix()
    matrix.loc[2015, "IDN"] = np.nan

    result = _fit(matrix)

    assert "IDN" not in result.weights
    assert result.dropped_donors == ("IDN",)
    assert "dropping donors" in caplog.text


def test_donor_missing_only_after_the_fit_window_is_kept():
    matrix = _matrix()
    matrix.loc[2023, "IDN"] = np.nan  # IDN has zero weight, so the synthetic survives

    result = _fit(matrix)

    assert "IDN" in result.weights
    assert result.synthetic.notna().all()


def test_synthetic_is_missing_where_a_weighted_donor_is_missing():
    matrix = _matrix()
    matrix.loc[2023, "VNM"] = np.nan  # VNM carries half the weight

    result = _fit(matrix)

    assert math.isnan(result.synthetic[2023])  # not silently reweighted


def test_too_few_complete_donors_raises():
    matrix = _matrix()
    matrix.loc[2014, ["KHM", "BGD", "LAO", "NPL"]] = np.nan

    with pytest.raises(ValueError, match="complete donors"):
        _fit(matrix)


def test_treated_unit_missing_data_in_the_fit_window_raises():
    matrix = _matrix()
    matrix.loc[2013, TREATED] = np.nan

    with pytest.raises(ValueError, match="missing"):
        _fit(matrix)


# --------------------------------------------------------------------------- #
# Variants
# --------------------------------------------------------------------------- #


def test_rebase_indexes_every_series_to_100_at_the_start():
    result = _fit(_matrix(), settings=replace(SETTINGS, rebase=True))

    assert result.actual[2011] == pytest.approx(100.0)
    assert result.synthetic[2011] == pytest.approx(100.0, abs=2.0)


def test_a_shorter_pre_period_leaves_the_gap_year_out_of_both_rmses():
    result = _fit(_matrix(effect=-100.0), settings=replace(SETTINGS, pre_end=2019))

    # 2020 is neither fit nor post: the pre-fit stays perfect.
    assert result.pre_rmse == pytest.approx(0.0, abs=1e-3)


def _covariates(matrix: pd.DataFrame, indicator: str = "SP.DYN.LE00.IN") -> pd.DataFrame:
    """A tidy covariate panel: a unit-specific constant for every year."""
    rng = np.random.default_rng(0)
    level = {unit: rng.uniform(60, 75) for unit in matrix.columns}
    return pd.DataFrame(
        [
            {
                config.COL_INDICATOR_ID: indicator,
                config.COL_COUNTRY_ISO3: unit,
                config.COL_YEAR: year,
                config.COL_VALUE: level[unit],
            }
            for unit in matrix.columns
            for year in YEARS
        ]
    )


def test_predictors_enter_the_fit_when_configured():
    matrix = _matrix()
    settings = replace(SETTINGS, predictors=("SP.DYN.LE00.IN",))

    result = _fit(matrix, settings=settings, covariates=_covariates(matrix))

    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_predictors_without_a_covariate_panel_raise():
    with pytest.raises(ValueError, match="covariate"):
        _fit(_matrix(), settings=replace(SETTINGS, predictors=("SP.DYN.LE00.IN",)))


def test_a_donor_missing_a_predictor_is_dropped():
    matrix = _matrix()
    covariates = _covariates(matrix)
    covariates = covariates[covariates[config.COL_COUNTRY_ISO3] != "LAO"]
    settings = replace(SETTINGS, predictors=("SP.DYN.LE00.IN",))

    result = _fit(matrix, settings=settings, covariates=covariates)

    assert "LAO" in result.dropped_donors


def test_poor_fit_is_flagged_relative_to_the_outcome_level():
    good = _fit(_matrix())
    matrix = _matrix()
    matrix[TREATED] = np.random.default_rng(1).uniform(200, 9_000, len(matrix))
    bad = _fit(matrix)

    assert not good.poor_fit
    assert bad.poor_fit
    assert bad.pre_rmse_share > config.SC_POOR_FIT_SHARE


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def _long(matrix: pd.DataFrame, **columns: str) -> pd.DataFrame:
    frame = matrix.stack().rename(config.COL_VALUE).reset_index()
    frame.columns = [config.COL_YEAR, config.COL_COUNTRY_ISO3, config.COL_VALUE]
    for column, value in columns.items():
        frame[column] = value
    return frame


def test_outcome_source_is_resolved_by_name():
    assert sc.resolve_outcome_source("NY.GDP.PCAP.KD") == "panel"
    assert sc.resolve_outcome_source("combined") == "index"
    with pytest.raises(ValueError, match="neither"):
        sc.resolve_outcome_source("vibes")


def test_outcome_matrix_reads_an_indicator_from_the_panel():
    panel = _long(_matrix(), **{config.COL_INDICATOR_ID: "NY.GDP.PCAP.KD"})

    wide = sc.outcome_matrix("NY.GDP.PCAP.KD", panel=panel)

    assert list(wide.columns) == [c for c in config.COUNTRY_CODES if c in wide.columns]
    assert wide.index.min() == config.MODELING_WINDOW_START


def test_outcome_matrix_reads_an_index_series_and_needs_its_source():
    index = _long(_matrix(), **{config.COL_SERIES: "combined"})

    assert sc.outcome_matrix("combined", index=index).shape == (len(YEARS), 7)
    with pytest.raises(ValueError, match="index"):
        sc.outcome_matrix("combined", panel=index)


def test_every_configured_outcome_resolves():
    for outcome in config.SC_OUTCOMES:
        assert sc.resolve_outcome_source(outcome.name) in {"panel", "index"}


# --------------------------------------------------------------------------- #
# Orchestration, tables and charts
# --------------------------------------------------------------------------- #


@pytest.fixture
def inputs(tmp_path):
    """Panel and index CSVs for both configured outcomes, with a known effect."""
    gdp = _matrix(effect=-200.0)
    combined = _matrix(effect=-80.0) / 10_000  # an index-like scale
    panel = _long(gdp, **{config.COL_INDICATOR_ID: "NY.GDP.PCAP.KD"})
    panel[config.COL_PRE_2011] = False
    index = _long(combined, **{config.COL_SERIES: "combined"})
    panel_path, index_path = tmp_path / "panel.csv", tmp_path / "index.csv"
    panel.to_csv(panel_path, index=False)
    index.to_csv(index_path, index=False)
    return panel_path, index_path


def test_run_writes_every_table_and_chart(tmp_path, inputs):
    panel_path, index_path = inputs

    result = counterfactual.run(
        panel_path=panel_path,
        index_path=index_path,
        output_dir=tmp_path / "processed",
        figures_dir=tmp_path / "figures",
        settings=SETTINGS,
    )

    stems = {
        config.SC_STEM,
        config.SC_WEIGHTS_STEM,
        config.SC_PLACEBO_STEM,
        config.SC_PLACEBO_TIME_STEM,
        config.SC_LEAVE_ONE_OUT_STEM,
        config.SC_METRICS_STEM,
    }
    assert {p.stem for p in result.written} == stems
    assert len(result.written) == len(stems) * len(config.OUTPUT_FORMATS)
    assert len(result.figures) == 3 * len(config.SC_OUTCOMES)
    for path in result.figures:
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_tables_have_the_documented_schemas(tmp_path, inputs):
    panel_path, index_path = inputs
    result = counterfactual.run(
        panel_path=panel_path,
        index_path=index_path,
        output_dir=tmp_path,
        figures_dir=tmp_path / "figures",
        settings=SETTINGS,
        render=False,
    )
    tables = result.tables

    assert list(tables[config.SC_STEM].columns) == ["outcome", "year", "series", "value"]
    assert set(tables[config.SC_STEM]["series"]) == {"actual", "synthetic", "gap"}
    assert list(tables[config.SC_WEIGHTS_STEM].columns) == [
        "outcome",
        "donor_iso3",
        "donor_name",
        "weight",
    ]
    assert list(tables[config.SC_PLACEBO_STEM].columns) == ["outcome", "unit_iso3", "year", "gap"]
    assert {
        "outcome",
        "pre_rmse",
        "post_rmse",
        "rmse_ratio",
        "pseudo_p_value",
        "n_effective_donors",
    } <= set(tables[config.SC_METRICS_STEM].columns)

    sums = tables[config.SC_WEIGHTS_STEM].groupby("outcome")["weight"].sum()
    assert sums.to_numpy() == pytest.approx(np.ones(len(sums)))
    # The placebo table carries the full ranked set: treated unit plus donors.
    units = tables[config.SC_PLACEBO_STEM].groupby("outcome")["unit_iso3"].nunique()
    assert (units == len(DONORS) + 1).all()


def test_cli_turns_a_missing_input_into_a_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        counterfactual.main(["--panel", str(tmp_path / "absent.csv"), "--no-figures"])

    assert exc.value.code == 2
    assert "make panel" in capsys.readouterr().err

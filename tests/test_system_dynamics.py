"""System-dynamics tests. Offline, synthetic and seeded.

The core construction: simulate history from known "true" parameters, turn it
into a panel, and check the calibration recovers them - then test the model's
qualitative behaviour (capital, the feedback loop, stability) on that footing.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from amber import config, dynamics
from amber.config import IndicatorLink, LinkKind, Scenario
from amber.modeling import system_dynamics as sd

INITIAL = sd.InitialState(
    year=config.SD_BACKTEST_START,
    output=1_000.0,
    connectivity=2.0,
    anchors={"SP.DYN.LE00.IN": 64.0, "SH.DYN.MORT": 60.0, "SE.SEC.ENRR": 50.0},
    growth=5.0,
)

TRUTH = {
    "stability_elasticity": 0.9,
    "tfp_growth": 0.015,
    "covid_shock": 0.12,
    "stability_post": 0.7,
    "human_capital_gain": 0.026,
    "connectivity_gain": 0.45,
    "population_growth": 0.7,
    "fdi_scale": 4.5,
    "mobile_saturation": 140.0,
    "mobile_scale": 14.0,
    "mortality_elasticity": -8.0,
    "enrollment_elasticity": 12.0,
    "health_share": 4.4,
}

NO_COUP = next(s for s in config.SCENARIOS if s.name == config.SD_COUNTERFACTUAL_SCENARIO)
ACTUAL = next(s for s in config.SCENARIOS if s.name == config.SD_BASELINE_SCENARIO)
FLAT = Scenario("flat", "Flat", ((config.SD_BACKTEST_START, 1.0),))


def _panel_from(frame: pd.DataFrame, country: str = config.TREATED_COUNTRY) -> pd.DataFrame:
    """A tidy panel of the modeled indicators from a simulated frame."""
    rows = [
        {
            config.COL_INDICATOR_ID: indicator_id,
            config.COL_INDICATOR_NAME: config.INDICATORS_BY_ID[indicator_id].name,
            config.COL_PILLAR: str(config.PILLAR_BY_INDICATOR[indicator_id]),
            config.COL_COUNTRY_ISO3: country,
            config.COL_COUNTRY_NAME: config.COUNTRIES[country],
            config.COL_YEAR: int(year),
            config.COL_VALUE: float(frame.loc[year, indicator_id]),
            config.COL_PRE_2011: year < config.MODELING_WINDOW_START,
        }
        for indicator_id in sd.modeled_indicators()
        for year in frame.index
    ]
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def truth_panel() -> pd.DataFrame:
    """History generated from TRUTH over the backtest window."""
    frame = sd.simulate(sd.historical_scenario(), TRUTH, INITIAL, end=config.SD_BACKTEST_END)
    return _panel_from(frame)


@pytest.fixture(scope="module")
def calibration(truth_panel) -> sd.Calibration:
    return sd.calibrate(truth_panel, restarts=2)


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def test_calibration_recovers_known_parameters(calibration):
    for name, true in TRUTH.items():
        assert calibration.params[name] == pytest.approx(true, rel=0.02, abs=1e-3), name


def test_backtest_error_is_near_zero_on_its_own_data(calibration, truth_panel):
    bt = sd.backtest(calibration, truth_panel)

    assert bt.overall == pytest.approx(0.0, abs=1e-3)
    assert bt.credible
    assert (bt.nrmse < 1e-2).all()


def test_fixed_parameters_are_not_fitted(calibration):
    for name, spec in config.SD_PARAMETERS.items():
        if not spec.calibrate:
            assert calibration.params[name] == spec.value
    assert set(calibration.fitted) == {n for n, p in config.SD_PARAMETERS.items() if p.calibrate}


def test_a_bad_calibration_fails_the_credibility_gate(calibration, truth_panel):
    params = {**calibration.params, "tfp_growth": 0.05, "stability_post": 0.2}
    bad = replace(calibration, params=params)

    bt = sd.backtest(bad, truth_panel)
    future = sd.FutureRun(calibration=bad, backtest=bt, results={})
    metrics = dynamics.metrics_table(future).set_index("scope")

    assert bt.overall > config.SD_CREDIBLE_NRMSE
    assert not bt.credible
    assert not metrics.loc["overall", "credible"]


# --------------------------------------------------------------------------- #
# Dynamics
# --------------------------------------------------------------------------- #


def test_capital_decays_monotonically_without_investment():
    frame = sd.simulate(FLAT, {**TRUTH, "savings_rate": 0.0}, INITIAL)

    assert (np.diff(frame["K"].to_numpy()) < 0).all()


def test_capital_grows_with_high_investment():
    frame = sd.simulate(FLAT, {**TRUTH, "savings_rate": 0.45}, INITIAL)

    assert (np.diff(frame["K"].to_numpy()) > 0).all()


def _slow_diffusion() -> dict[str, float]:
    """Connectivity still mid-diffusion when the levers start, so they can bite."""
    return {**TRUTH, "connectivity_gain": 0.12}


def test_connectivity_investment_raises_long_run_output_and_the_index():
    boosted = Scenario("boost", "Boost", FLAT.stability, levers={"connectivity_investment": 2.0})
    base = sd.simulate(FLAT, _slow_diffusion(), INITIAL)
    more = sd.simulate(boosted, _slow_diffusion(), INITIAL)
    end = config.SD_HORIZON_END

    assert more.loc[end, "I"] > base.loc[end, "I"]
    assert more.loc[end, "Y"] > base.loc[end, "Y"]
    assert more.loc[end, config.COMBINED_SERIES] > base.loc[end, config.COMBINED_SERIES]


def test_the_output_gain_runs_through_the_connectivity_tfp_link():
    """Cut kappa and connectivity no longer lifts output: the loop carries it."""
    boosted = Scenario("boost", "Boost", FLAT.stability, levers={"connectivity_investment": 2.0})
    no_loop = {**_slow_diffusion(), "connectivity_tfp": 0.0}
    end = config.SD_HORIZON_END

    base = sd.simulate(FLAT, no_loop, INITIAL)
    more = sd.simulate(boosted, no_loop, INITIAL)

    assert more.loc[end, "I"] > base.loc[end, "I"]
    assert more.loc[end, "Y"] == pytest.approx(base.loc[end, "Y"])


def test_output_feeds_back_into_connectivity_diffusion():
    richer = sd.simulate(FLAT, {**_slow_diffusion(), "tfp_growth": 0.04}, INITIAL)
    poorer = sd.simulate(FLAT, {**_slow_diffusion(), "tfp_growth": 0.0}, INITIAL)

    year = config.SD_PROJECTION_START
    assert richer.loc[year, "I"] > poorer.loc[year, "I"]


def test_higher_stability_ends_higher():
    no_coup = sd.simulate(NO_COUP, TRUTH, INITIAL)
    actual = sd.simulate(ACTUAL, TRUTH, INITIAL)
    end = config.SD_HORIZON_END

    assert no_coup.loc[end, config.COMBINED_SERIES] > actual.loc[end, config.COMBINED_SERIES]
    assert no_coup.loc[end, "Y"] > actual.loc[end, "Y"]


def test_scenarios_match_until_they_diverge():
    no_coup = sd.simulate(NO_COUP, TRUTH, INITIAL)
    actual = sd.simulate(ACTUAL, TRUTH, INITIAL)
    before = config.TREATMENT_YEAR - 1

    pd.testing.assert_series_equal(no_coup.loc[:before, "Y"], actual.loc[:before, "Y"])
    assert sd.divergence_year(NO_COUP) == config.TREATMENT_YEAR
    assert sd.divergence_year(ACTUAL) is None


def test_covid_is_a_persistent_level_loss():
    covid = sd.simulate(FLAT, TRUTH, INITIAL)
    none = sd.simulate(FLAT, {**TRUTH, "covid_shock": 0.0}, INITIAL)
    first = min(config.COVID_CONFOUNDED_YEARS)

    assert covid.loc[first - 1, "Y"] == pytest.approx(none.loc[first - 1, "Y"])
    # Still below the no-COVID path years later - no V-shaped rebound.
    assert covid.loc[first + 4, "Y"] < none.loc[first + 4, "Y"]


def test_connectivity_saturates_below_its_goalpost():
    frame = sd.simulate(FLAT, {**TRUTH, "connectivity_gain": 3.0}, INITIAL)

    assert frame["I"].max() <= config.GOALPOSTS[config.SD_CONNECTIVITY_INDICATOR].high


def test_bounded_enrollment_approaches_but_never_passes_its_ceiling():
    frame = sd.simulate(FLAT, {**TRUTH, "human_capital_gain": 0.1}, INITIAL)
    ceiling = config.GOALPOSTS["SE.SEC.ENRR"].high

    assert frame["SE.SEC.ENRR"].max() < ceiling
    assert (np.diff(frame["SE.SEC.ENRR"].to_numpy()) > 0).all()


# --------------------------------------------------------------------------- #
# Index integration
# --------------------------------------------------------------------------- #


def test_projected_index_lands_between_floor_and_one():
    frame = sd.simulate(NO_COUP, TRUTH, INITIAL)
    series = [*(str(p) for p in config.Pillar), config.COMBINED_SERIES]

    values = frame[series].to_numpy()
    assert np.isfinite(values).all()
    assert (values >= config.NORMALIZED_FLOOR).all()
    assert (values <= 1.0).all()


def test_a_projection_past_a_goalpost_clips_with_a_warning(caplog):
    heavy = Scenario("heavy", "Heavy", FLAT.stability, levers={"health_spend": 2.0})
    frame = sd.simulate(heavy, {**TRUTH, "health_share": 8.0}, INITIAL)

    assert frame["SH.XPD.CHEX.GD.ZS"].max() > config.GOALPOSTS["SH.XPD.CHEX.GD.ZS"].high
    assert "outside their goalposts" in caplog.text
    assert frame[config.COMBINED_SERIES].max() <= 1.0


def test_excluded_indicators_are_not_projected():
    frame = sd.simulate(FLAT, TRUTH, INITIAL)
    excluded = [i for i, link in config.SD_INDICATOR_LINKS.items() if link.kind == "excluded"]

    assert excluded
    assert not set(excluded) & set(frame.columns)


# --------------------------------------------------------------------------- #
# Ensemble
# --------------------------------------------------------------------------- #


def test_same_seed_gives_identical_trajectories_and_bands(calibration):
    first = sd.run_scenarios(calibration, [NO_COUP], size=12, seed=5)[NO_COUP.name]
    second = sd.run_scenarios(calibration, [NO_COUP], size=12, seed=5)[NO_COUP.name]

    pd.testing.assert_frame_equal(first.central, second.central)
    pd.testing.assert_frame_equal(first.bands, second.bands)


def test_a_different_seed_changes_the_band(calibration):
    first = sd.run_scenarios(calibration, [NO_COUP], size=12, seed=5)[NO_COUP.name]
    other = sd.run_scenarios(calibration, [NO_COUP], size=12, seed=6)[NO_COUP.name]

    assert not first.bands[config.COL_VALUE].equals(other.bands[config.COL_VALUE])


def test_member_zero_is_the_calibration_and_bands_are_ordered(calibration):
    result = sd.run_scenarios(calibration, [NO_COUP], size=40, seed=5)[NO_COUP.name]
    direct = sd.simulate(NO_COUP, calibration.params, calibration.initial)
    combined = config.COMBINED_SERIES

    pd.testing.assert_series_equal(
        result.central[combined], direct[combined], check_names=False, atol=1e-9
    )
    low, mid, high = (result.band(combined, q) for q in ("p10", "p50", "p90"))
    assert (low <= mid + 1e-12).all()
    assert (mid <= high + 1e-12).all()


def test_scenarios_share_parameter_draws(calibration):
    """Common random numbers: before divergence, every scenario's band is identical."""
    results = sd.run_scenarios(calibration, [NO_COUP, ACTUAL], size=20, seed=3)
    before = config.TREATMENT_YEAR - 1

    for q in config.SD_QUANTILES:
        a = results[NO_COUP.name].band("Y", q).loc[:before]
        b = results[ACTUAL.name].band("Y", q).loc[:before]
        pd.testing.assert_series_equal(a, b, check_names=False)


# --------------------------------------------------------------------------- #
# Consistency with phase 3
# --------------------------------------------------------------------------- #


def _sc_tables(result: sd.SimulationResult, scale: float, credible: bool) -> tuple:
    gdp = config.SD_OUTPUT_INDICATOR
    years = range(config.TREATMENT_YEAR, config.SD_BACKTEST_END + 1)
    median = result.band(gdp, "p50")
    paths = pd.DataFrame(
        {
            config.COL_OUTCOME: gdp,
            config.COL_YEAR: list(years),
            config.COL_SERIES: "synthetic",
            config.COL_VALUE: [median[y] * scale for y in years],
        }
    )
    metrics = pd.DataFrame({config.COL_OUTCOME: [gdp], "credible": [credible]})
    return paths, metrics


def test_sc_overlap_deviation_is_computed_and_judged(calibration):
    result = sd.run_scenarios(calibration, [NO_COUP], size=8, seed=1)[NO_COUP.name]

    close = sd.sc_consistency(result, *_sc_tables(result, 1.05, credible=True))[0]
    far = sd.sc_consistency(result, *_sc_tables(result, 1.5, credible=True))[0]

    assert close.deviation == pytest.approx(1 - 1 / 1.05, rel=1e-6)
    assert close.consistent is True
    assert far.consistent is False
    assert close.years == tuple(range(config.TREATMENT_YEAR, config.SD_BACKTEST_END + 1))


def test_sc_consistency_is_not_applicable_against_a_non_credible_sc(calibration):
    result = sd.run_scenarios(calibration, [NO_COUP], size=8, seed=1)[NO_COUP.name]

    check = sd.sc_consistency(result, *_sc_tables(result, 1.0, credible=False))[0]

    assert math.isnan(check.deviation)
    assert check.consistent is None
    assert not check.sc_credible


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #


def test_the_shipped_config_validates():
    config._check_system_dynamics_config()


def test_a_scenario_naming_an_unknown_lever_fails():
    bad = Scenario("bad", "Bad", FLAT.stability, levers={"vibes": 1.0})
    with pytest.raises(ValueError, match="unknown levers"):
        config._check_system_dynamics_config(scenarios=[*config.SCENARIOS, bad])


def test_a_scenario_lever_outside_its_range_fails():
    bad = Scenario("bad", "Bad", FLAT.stability, levers={"health_spend": 9.0})
    with pytest.raises(ValueError, match="outside its range"):
        config._check_system_dynamics_config(scenarios=[*config.SCENARIOS, bad])


def test_a_mapping_gap_fails():
    links = dict(config.SD_INDICATOR_LINKS)
    links.pop("SP.DYN.LE00.IN")
    with pytest.raises(ValueError, match="out of step"):
        config._check_system_dynamics_config(links=links)


def test_a_link_naming_an_unknown_parameter_fails():
    links = {**config.SD_INDICATOR_LINKS, "SH.DYN.MORT": IndicatorLink(LinkKind.ELASTICITY, ("x",))}
    with pytest.raises(ValueError, match="unknown parameters"):
        config._check_system_dynamics_config(links=links)


def test_an_exclusion_without_a_reason_fails():
    links = {**config.SD_INDICATOR_LINKS, "SI.POV.DDAY": IndicatorLink(LinkKind.EXCLUDED)}
    with pytest.raises(ValueError, match="documented reason"):
        config._check_system_dynamics_config(links=links)


def test_a_missing_required_scenario_fails():
    kept = [s for s in config.SCENARIOS if s.name != config.SD_COUNTERFACTUAL_SCENARIO]
    with pytest.raises(ValueError, match="required"):
        config._check_system_dynamics_config(scenarios=kept)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def test_dynamics_run_writes_every_table_and_chart(tmp_path, truth_panel, monkeypatch):
    monkeypatch.setattr(config, "SD_ENSEMBLE_SIZE", 10)  # captions quote it
    panel_path = tmp_path / "panel.csv"
    truth_panel.to_csv(panel_path, index=False)

    result = dynamics.run(
        panel_path=panel_path,
        sc_paths_path=tmp_path / "absent_sc.csv",  # phase 3 not run: check is skipped
        sc_metrics_path=tmp_path / "absent_metrics.csv",
        output_dir=tmp_path / "processed",
        figures_dir=tmp_path / "figures",
        size=10,
    )

    stems = {
        config.SD_TRAJECTORY_STEM,
        config.SD_SCENARIOS_STEM,
        config.SD_CALIBRATION_STEM,
        config.SD_METRICS_STEM,
    }
    assert {p.stem for p in result.written} == stems
    assert len(result.figures) == 4
    for path in result.figures:
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    trajectory = result.tables[config.SD_TRAJECTORY_STEM]
    assert list(trajectory.columns) == ["scenario", "year", "series", "quantile", "value"]
    assert set(trajectory["quantile"]) == set(config.SD_QUANTILES)
    assert {"K", "H", "I", "S", "Y", config.COMBINED_SERIES} <= set(trajectory["series"])
    assert set(trajectory["scenario"]) == {s.name for s in config.SCENARIOS}

    metrics = result.tables[config.SD_METRICS_STEM]
    assert {"scope", "nrmse", "credible", "sc_overlap_deviation"} <= set(metrics.columns)
    assert metrics.loc[metrics["scope"] == "overall", "credible"].item()


def test_calibration_table_flags_parameters_at_a_bound(calibration):
    pinned = {**calibration.params, "covid_shock": config.SD_PARAMETERS["covid_shock"].high}
    table = dynamics.calibration_table(replace(calibration, params=pinned)).set_index("parameter")

    assert table.loc["covid_shock", "at_bound"]
    assert not table.loc["tfp_growth", "at_bound"]
    assert not table.loc["alpha", "at_bound"]  # fixed parameters are never "at a bound"


def test_scenarios_table_lists_every_lever_and_stability():
    table = dynamics.scenarios_table()

    for scenario in config.SCENARIOS:
        rows = table[table["scenario"] == scenario.name]
        assert set(config.LEVERS) <= set(rows["lever"])
        assert f"stability_recovery_{config.SD_HORIZON_END}" in set(rows["lever"])


def test_captions_follow_the_credibility_gate(calibration, truth_panel):
    from amber import figures

    good = sd.FutureRun(calibration, sd.backtest(calibration, truth_panel), results={})
    params = {**calibration.params, "tfp_growth": 0.05, "stability_post": 0.2}
    bad_cal = replace(calibration, params=params)
    bad = sd.FutureRun(bad_cal, sd.backtest(bad_cal, truth_panel), results={})

    assert figures._gate_phrase(good).startswith("Scenarios, not forecasts")
    assert "not a calibrated projection" in figures._gate_phrase(bad)


def test_cli_turns_a_missing_panel_into_a_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        dynamics.main(["--panel", str(tmp_path / "absent.csv"), "--no-figures"])

    assert exc.value.code == 2
    assert "make panel" in capsys.readouterr().err

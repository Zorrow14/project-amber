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


@pytest.fixture(scope="module")
def nodes(calibration, truth_panel) -> tuple[sd.ProfileNode, ...]:
    return sd.profile(calibration, truth_panel, restarts=1)


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


def test_fixing_a_calibrated_parameter_is_refused(truth_panel):
    with pytest.raises(ValueError, match="non-calibrated"):
        sd.calibrate(truth_panel, restarts=1, fixed={"tfp_growth": 0.01})


def test_combined_backtest_is_like_for_like_where_indicators_go_dark(calibration, truth_panel):
    # Internet stops being reported after 2020, as in Myanmar's real data.
    dark = (truth_panel[config.COL_INDICATOR_ID] == "IT.NET.USER.ZS") & (
        truth_panel[config.COL_YEAR] > 2020
    )
    bt = sd.backtest(calibration, truth_panel[~dark])

    # Matched scoring drops the same cells, so on its own data it tracks history.
    assert bt.combined_nrmse == pytest.approx(0.0, abs=2e-3)
    assert bt.combined_coverage[2024] < 1.0
    assert bt.combined_coverage[2015] == 1.0
    # All indicators are modeled every year, so the full-composition index departs
    # from history after 2020 by composition alone - reported, not hidden.
    assert bt.last_observed_year == config.SD_BACKTEST_END
    assert abs(bt.composition_gap) > 1e-3
    assert bt.fit_gap == pytest.approx(0.0, abs=2e-3)
    assert bt.composition_gap == pytest.approx(
        bt.combined_modeled[2024] - bt.combined_matched[2024]
    )


def test_with_every_indicator_observed_there_is_no_composition_gap(calibration, truth_panel):
    bt = sd.backtest(calibration, truth_panel)

    pd.testing.assert_series_equal(
        bt.combined_matched, bt.combined_modeled, check_names=False, atol=1e-12
    )
    assert bt.composition_gap == pytest.approx(0.0, abs=1e-12)


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


def test_the_model_produces_exactly_the_index_indicators():
    frame = sd.simulate(FLAT, TRUTH, INITIAL)
    produced = [c for c in frame.columns if c in config.INDICATORS_BY_ID]

    # Same composition as the historical index, so the two never splice.
    assert produced == list(config.INDEX_INDICATORS)
    assert not set(config.INDEX_EXCLUDED) & set(frame.columns)


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
# Unidentified parameters and paired gaps
# --------------------------------------------------------------------------- #


def test_kappa_and_the_savings_rate_are_the_unidentified_parameters():
    assert set(sd.UNIDENTIFIED) == {"connectivity_tfp", "savings_rate"}
    # gamma, the stability lever's strength, stays estimated.
    assert config.SD_PARAMETERS["stability_elasticity"].calibrate


def test_profile_refits_every_low_assumed_high_combination(nodes, calibration):
    assert len(nodes) == 3 ** len(sd.UNIDENTIFIED)
    assert nodes[0].central and nodes[0].calibration is calibration
    assert not any(node.central for node in nodes[1:])
    combos = {tuple(sorted(node.values.items())) for node in nodes}
    assert len(combos) == len(nodes)
    for node in nodes:
        for name, value in node.values.items():
            assert node.calibration.params[name] == value
            spec = config.SD_PARAMETERS[name]
            assert value in {spec.low, spec.value, spec.high}
    # Off-centre nodes are refitted, not copies of the central fit.
    assert any(
        node.calibration.params["tfp_growth"] != calibration.params["tfp_growth"]
        for node in nodes[1:]
    )


def test_a_profile_node_beyond_tolerance_is_not_flat(nodes):
    steep = replace(nodes[1], nrmse_change=config.SD_PROFILE_TOLERANCE * 2)
    assert nodes[0].flat
    assert not steep.flat


def test_ensemble_members_cycle_through_the_profile_nodes(nodes):
    fits = [node.calibration for node in nodes]
    params = sd._ensemble(fits, size=1 + 2 * len(fits), jitter=0.0, seed=1)

    kappa = params["connectivity_tfp"]
    assert kappa[0] == config.SD_PARAMETERS["connectivity_tfp"].value
    spec = config.SD_PARAMETERS["connectivity_tfp"]
    assert set(kappa) == {spec.low, spec.value, spec.high}
    for m in range(1, kappa.size):
        assert kappa[m] == fits[(m - 1) % len(fits)].params["connectivity_tfp"]


def test_profile_nodes_widen_the_band(calibration, nodes):
    def width(result: sd.SimulationResult) -> float:
        gdp = config.SD_OUTPUT_INDICATOR
        return float(result.band(gdp, "p90").iloc[-1] - result.band(gdp, "p10").iloc[-1])

    narrow = sd.run_scenarios(calibration, [NO_COUP], size=40, seed=3)[NO_COUP.name]
    wide = sd.run_scenarios(calibration, [NO_COUP], size=40, seed=3, nodes=nodes)[NO_COUP.name]

    assert width(wide) > width(narrow)


def test_paired_gaps_are_member_by_member_against_the_baseline(calibration, nodes):
    results = sd.run_scenarios(calibration, [ACTUAL, NO_COUP], size=30, seed=4, nodes=nodes)

    assert results[ACTUAL.name].gaps is None
    gaps = results[NO_COUP.name].gaps
    assert gaps is not None
    assert set(gaps[config.COL_SERIES]) == set(config.SD_GAP_SERIES)
    gdp = gaps[gaps[config.COL_SERIES] == config.SD_OUTPUT_INDICATOR].set_index(config.COL_YEAR)
    # Identical until the coup, then no coup pulls ahead in every member.
    assert gdp.loc[2019, ["p10", "p50", "p90"]].abs().max() < 1e-9
    assert gdp.loc[config.SD_HORIZON_END, "share_above"] == 1.0
    assert (gdp["p10"] <= gdp["p50"]).all() and (gdp["p50"] <= gdp["p90"]).all()


def test_paired_gap_without_spread_is_the_central_difference(calibration):
    results = sd.run_scenarios(calibration, [ACTUAL, NO_COUP], size=1, seed=4)
    gaps = results[NO_COUP.name].gaps
    assert gaps is not None
    gdp = gaps[gaps[config.COL_SERIES] == config.SD_OUTPUT_INDICATOR].set_index(config.COL_YEAR)
    central = results[NO_COUP.name].central["Y"] - results[ACTUAL.name].central["Y"]

    np.testing.assert_allclose(gdp["p50"].to_numpy(), central.to_numpy())


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
    with pytest.raises(ValueError, match="must cover the index indicators"):
        config._check_system_dynamics_config(links=links)


def test_a_link_naming_an_unknown_parameter_fails():
    links = {**config.SD_INDICATOR_LINKS, "SH.DYN.MORT": IndicatorLink(LinkKind.ELASTICITY, ("x",))}
    with pytest.raises(ValueError, match="unknown parameters"):
        config._check_system_dynamics_config(links=links)


def test_linking_an_indicator_outside_the_index_fails():
    links = {**config.SD_INDICATOR_LINKS, "SI.POV.DDAY": IndicatorLink(LinkKind.HUMAN_CAPITAL)}
    with pytest.raises(ValueError, match="must cover the index indicators"):
        config._check_system_dynamics_config(links=links)


def test_an_unidentified_parameter_needs_a_fixed_value_and_a_range():
    params = dict(config.SD_PARAMETERS)
    params["tfp_growth"] = replace(params["tfp_growth"], unidentified=True)  # calibrated
    with pytest.raises(ValueError, match="unidentified"):
        config._check_system_dynamics_config(parameters=params)
    params = dict(config.SD_PARAMETERS)
    params["delta_k"] = replace(params["delta_k"], unidentified=True)  # no range
    with pytest.raises(ValueError, match="unidentified"):
        config._check_system_dynamics_config(parameters=params)


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
        config.SD_PROFILE_STEM,
        config.SD_GAPS_STEM,
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

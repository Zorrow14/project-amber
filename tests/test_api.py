"""API tests. Offline: they serve the committed release snapshot, never fit anything.

Every fitting entry point - SD calibration and profiling, and every synthetic-
control fit - is replaced with one that fails the test, so an endpoint that
recomputed a model instead of serving or cheaply re-running it would be caught.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from amber import config, release
from amber.api.main import create_app
from amber.api.settings import Settings
from amber.api.store import DataStore, DataUnavailableError, load_store
from amber.config import DataSource
from amber.modeling import synthetic_control as sc
from amber.modeling import system_dynamics as sd

RELEASE = config.RELEASE_DATA_DIR
GDP = config.GDP_PC_INDICATOR
FORBIDDEN = {
    sd: ("calibrate", "profile", "backtest"),
    sc: ("fit_synthetic_control", "run_placebo_space", "run_placebo_time", "leave_one_out", "run"),
}


@pytest.fixture(autouse=True, scope="module")
def _no_fitting() -> Iterator[None]:
    """Make any model fit fail loudly: the API must only serve and re-run."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        msg = "The API must never fit a model on a request"
        raise AssertionError(msg)

    with pytest.MonkeyPatch.context() as patch:
        for module, names in FORBIDDEN.items():
            for name in names:
                patch.setattr(module, name, forbidden)
        yield


@pytest.fixture(scope="module")
def store() -> DataStore:
    return load_store(DataSource.RELEASE, RELEASE)


def _client(store: DataStore, origins: tuple[str, ...] = ("http://localhost:5173",)) -> TestClient:
    settings = Settings(data_source=store.source, data_dir=store.data_dir, cors_origins=origins)
    return TestClient(create_app(settings=settings, store=store))


@pytest.fixture(scope="module")
def client(store) -> Iterator[TestClient]:
    with _client(store) as test_client:
        yield test_client


def _copy_release(tmp_path: Path) -> Path:
    """A writable copy of the snapshot, served as ``processed`` (no hash check)."""
    target = tmp_path / "data"
    shutil.copytree(RELEASE, target)
    (target / config.RELEASE_MANIFEST).unlink()
    return target


def _edit_bool(path: Path, key_col: str, key: str, col: str, value: bool) -> None:
    frame = pd.read_csv(path)
    frame.loc[frame[key_col] == key, col] = value
    frame.to_csv(path, index=False)


# --------------------------------------------------------------------------- #
# Health and meta
# --------------------------------------------------------------------------- #


def test_health_reports_the_snapshot(client):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["data"]["source"] == "release"
    assert body["data"]["built_at"]


def test_meta_is_derived_from_config(client):
    body = client.get("/meta").json()

    assert body["treatment_year"] == config.TREATMENT_YEAR
    assert body["modeling_window"] == {
        "start": config.MODELING_WINDOW_START,
        "end": config.YEAR_END,
    }
    assert body["horizon_end"] == config.SD_HORIZON_END
    assert [c["iso3"] for c in body["countries"]] == list(config.COUNTRIES)
    assert [c["iso3"] for c in body["countries"] if c["treated"]] == [config.TREATED_COUNTRY]
    levers = {lever["name"]: lever for lever in body["levers"]}
    assert set(levers) == set(config.LEVERS)
    for name, lever in config.LEVERS.items():
        assert (levers[name]["min"], levers[name]["max"]) == (lever.low, lever.high)
        assert levers[name]["default"] == lever.default
        assert levers[name]["label"] and levers[name]["step"] > 0
    assert [s["name"] for s in body["scenarios"]] == [s.name for s in config.SCENARIOS]
    reform = next(s for s in body["scenarios"] if s["name"] == "reform_push")
    assert reform["levers"]["education_spend"] == 1.5
    assert set(reform["levers"]) == set(config.LEVERS)
    assert {p["id"]: p["default_weight"] for p in body["pillars"]} == {
        str(p): w for p, w in config.DEFAULT_PILLAR_WEIGHTS.items()
    }
    excluded = {i["id"]: i["excluded_reason"] for i in body["indicators"] if not i["in_index"]}
    assert excluded == config.INDEX_EXCLUDED
    assert body["framing"]["project"] == config.PROJECT_FRAMING


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #


def test_panel_defaults_to_gdp_per_capita_for_every_country(client):
    body = client.get("/panel").json()

    assert body["indicators"] == [GDP]
    assert set(body["countries"]) == set(config.COUNTRIES)
    assert {r["indicator_id"] for r in body["rows"]} == {GDP}
    assert min(r["year"] for r in body["rows"]) == config.MODELING_WINDOW_START
    assert len(body["coverage"]) == len(config.COUNTRIES)


def test_panel_filters_and_flags_dark_series(client):
    body = client.get("/panel?indicators=IT.NET.USER.ZS&countries=MMR").json()

    assert {(r["country_iso3"], r["indicator_id"]) for r in body["rows"]} == {
        ("MMR", "IT.NET.USER.ZS")
    }
    (coverage,) = body["coverage"]
    assert coverage["is_dark"] is True  # Myanmar's internet series stops after 2020


def test_panel_can_include_the_pre_window_years(client):
    body = client.get("/panel?countries=MMR&include_pre_window=true").json()
    assert min(r["year"] for r in body["rows"]) == config.YEAR_START


@pytest.mark.parametrize("query", ["indicators=NOPE", "countries=FRA", "indicators=,"])
def test_panel_rejects_unknown_names(client, query):
    assert client.get(f"/panel?{query}").status_code == 422


# --------------------------------------------------------------------------- #
# Index (live)
# --------------------------------------------------------------------------- #


def _combined(body: dict, iso3: str = config.TREATED_COUNTRY) -> pd.Series:
    rows = [
        r
        for r in body["rows"]
        if r["country_iso3"] == iso3 and r["series"] == config.COMBINED_SERIES
    ]
    return pd.Series({r["year"]: r["value"] for r in rows})


def test_default_index_matches_the_published_index(client):
    body = client.get("/index").json()
    published = pd.read_csv(RELEASE / f"{config.INDEX_STEM}.csv")

    live = pd.DataFrame(body["rows"]).sort_values(["country_iso3", "series", "year"])
    published = published.sort_values(["country_iso3", "series", "year"])
    assert body["computed_live"] is True
    assert len(live) == len(published)
    assert live["value"].to_numpy() == pytest.approx(published["value"].to_numpy())
    assert live["coverage"].to_numpy() == pytest.approx(published["coverage"].to_numpy())


def test_index_weights_change_the_combined_series(client):
    def combined(weights: str) -> pd.Series:
        return _combined(client.get(f"/index?weights={weights}").json())

    equal = _combined(client.get("/index").json())
    tilted = combined("economy=3,innovation=1,human_development=1")
    rescaled = combined("economy=2,innovation=2,human_development=2")

    assert not tilted.equals(equal)
    assert (tilted - equal).abs().max() > 1e-3
    pd.testing.assert_series_equal(rescaled, equal)  # any scale, same index


def test_index_reports_applied_weights_and_coverage(client):
    body = client.get("/index?weights=economy=2,innovation=1,human_development=1").json()

    assert body["weights"] == pytest.approx(
        {"economy": 0.5, "innovation": 0.25, "human_development": 0.25}
    )
    assert body["coverage_note"] == config.COVERAGE_MESSAGE
    mmr_2024 = [
        r
        for r in body["rows"]
        if r["country_iso3"] == "MMR" and r["year"] == 2024 and r["series"] == "combined"
    ]
    assert mmr_2024[0]["coverage"] < 1  # partial coverage is visible in the payload


@pytest.mark.parametrize(
    "query",
    [
        "weights=economy=1,innovation=1,culture=1",  # unknown pillar
        "weights=economy=1,innovation=1",  # missing pillar
        "weights=economy=-1,innovation=1,human_development=1",  # negative
        "weights=economy=0,innovation=0,human_development=0",  # all zero
        "weights=economy=abc,innovation=1,human_development=1",  # not a number
        "weights=economy",  # malformed
        "weights=economy=inf,innovation=1,human_development=1",  # non-finite
        "method=zscore",  # unknown method
    ],
)
def test_index_rejects_bad_weights_with_422(client, query):
    response = client.get(f"/index?{query}")
    assert response.status_code == 422
    assert response.json()["detail"]


# --------------------------------------------------------------------------- #
# Counterfactual (precomputed)
# --------------------------------------------------------------------------- #


def test_counterfactual_carries_series_weights_placebos_and_verdicts(client):
    body = client.get("/counterfactual").json()
    metrics = pd.read_csv(RELEASE / f"{config.SC_METRICS_STEM}.csv").set_index("outcome")

    assert [o["outcome"] for o in body["outcomes"]] == [o.name for o in config.SC_OUTCOMES]
    for outcome in body["outcomes"]:
        name = outcome["outcome"]
        m = outcome["metrics"]
        assert outcome["credibility"]["credible"] == bool(metrics.loc[name, "credible"])
        assert m["pre_rmse_share"] == pytest.approx(metrics.loc[name, "pre_rmse_share"])
        assert m["pseudo_p_value"] == pytest.approx(metrics.loc[name, "pseudo_p_value"])
        assert m["n_effective_donors"] == pytest.approx(metrics.loc[name, "n_effective_donors"])
        assert m["n_weighted_donors"] == metrics.loc[name, "n_weighted_donors"]
        assert m["p_value_floor"] == pytest.approx(1 / m["n_units"])
        assert sum(w["weight"] for w in outcome["weights"]) == pytest.approx(1.0, abs=1e-6)
        assert outcome["latest"]["year"] == config.YEAR_END
        assert {p["unit_iso3"] for p in outcome["placebos"]} == set(config.COUNTRIES)
        assert next(p for p in outcome["placebos"] if p["treated"])["poor_fit"] is False
        assert outcome["leave_one_out"] and outcome["leave_one_out_band"]
        assert outcome["placebo_time"]["placebo_year"] == config.SC_INTIME_PLACEBO_YEAR


def test_a_non_credible_counterfactual_says_so(client):
    body = client.get("/counterfactual").json()
    combined = next(o for o in body["outcomes"] if o["outcome"] == config.COMBINED_SERIES)
    gdp = next(o for o in body["outcomes"] if o["outcome"] == GDP)

    assert combined["credibility"]["credible"] is False
    assert combined["credibility"]["message"] == config.SC_NOT_CREDIBLE_MESSAGE
    assert gdp["credibility"]["credible"] is True
    assert gdp["credibility"]["message"] is None
    assert gdp["metrics"]["rank"] == 1


def test_poor_fit_placebos_follow_the_phase3_multiple(client):
    body = client.get("/counterfactual").json()
    gdp = next(o for o in body["outcomes"] if o["outcome"] == GDP)
    treated = next(p for p in gdp["placebos"] if p["treated"])

    assert treated["pre_rmse"] == pytest.approx(gdp["metrics"]["pre_rmse"])
    for placebo in gdp["placebos"]:
        limit = config.SC_PLACEBO_POOR_FIT_MULTIPLE * treated["pre_rmse"]
        assert placebo["poor_fit"] == (not placebo["treated"] and placebo["pre_rmse"] > limit)


# --------------------------------------------------------------------------- #
# Scenarios (precomputed) and simulate (live)
# --------------------------------------------------------------------------- #


def _assert_scenario_shape(result: dict, years: list[int]) -> None:
    expected = {*sd.STOCKS, *config.INDEX_INDICATORS, *config.INDEX_SERIES}
    assert set(result["series"]) == expected
    for bands in result["series"].values():
        assert set(bands) == set(config.SD_QUANTILES)
        assert all(len(values) == len(years) for values in bands.values())
    assert set(result["levers"]) == set(config.LEVERS)
    assert result["sc_checks"]


def test_scenarios_carry_every_band_and_the_models_verdicts(client):
    body = client.get("/scenarios").json()
    years = body["years"]

    assert years[0] == config.SD_BACKTEST_START and years[-1] == config.SD_HORIZON_END
    assert [r["name"] for r in body["scenarios"]] == [s.name for s in config.SCENARIOS]
    for result in body["scenarios"]:
        _assert_scenario_shape(result, years)
    credibility = body["credibility"]
    assert credibility["credible"] is True
    assert credibility["framing"] == config.SCENARIO_FRAMING
    assert credibility["composition_gap"] is not None
    assert {m["scope"] for m in credibility["metrics"]} >= {"overall", config.COMBINED_SERIES}
    assert body["history"]["combined_coverage"][-1] < 1


def test_paired_gaps_and_sc_checks_are_in_the_scenarios(client):
    body = client.get("/scenarios").json()
    by_name = {r["name"]: r for r in body["scenarios"]}

    assert by_name[config.SD_BASELINE_SCENARIO]["gaps"] is None
    gaps = by_name[config.SD_COUNTERFACTUAL_SCENARIO]["gaps"][GDP]
    assert gaps["share_above"][-1] == 1.0
    checks = {c["outcome"]: c for c in by_name[config.SD_COUNTERFACTUAL_SCENARIO]["sc_checks"]}
    assert checks[GDP]["applicable"] and checks[GDP]["consistent"] is True
    assert checks[GDP]["deviation"] == pytest.approx(0.052, abs=0.01)
    assert checks[config.COMBINED_SERIES]["sc_credible"] is False
    assert checks[config.COMBINED_SERIES]["deviation"] is None
    baseline = {c["outcome"]: c for c in by_name[config.SD_BASELINE_SCENARIO]["sc_checks"]}
    assert baseline[GDP]["applicable"] is False and baseline[GDP]["reason"]


def test_simulating_a_named_scenario_reproduces_the_precomputed_run(client):
    precomputed = next(
        r
        for r in client.get("/scenarios").json()["scenarios"]
        if r["name"] == config.SD_COUNTERFACTUAL_SCENARIO
    )
    live = client.post("/simulate", json={"scenario": config.SD_COUNTERFACTUAL_SCENARIO}).json()

    assert live["result"]["custom"] is False
    for series, bands in precomputed["series"].items():
        for quantile, values in bands.items():
            assert live["result"]["series"][series][quantile] == pytest.approx(
                values, rel=1e-9, abs=1e-9
            ), (series, quantile)


def test_a_lever_change_moves_the_trajectory(client):
    base = client.post("/simulate", json={"scenario": "no_coup"}).json()["result"]
    pushed = client.post(
        "/simulate", json={"scenario": "no_coup", "levers": {"education_spend": 2.0}}
    ).json()["result"]

    assert pushed["custom"] is True
    assert pushed["levers"]["education_spend"] == 2.0
    assert pushed["series"]["H"]["p50"][-1] > base["series"]["H"]["p50"][-1]
    assert pushed["series"]["combined"]["p50"][-1] > base["series"]["combined"]["p50"][-1]
    # Levers apply from the projection start, so history is untouched.
    first = config.SD_PROJECTION_START - config.SD_BACKTEST_START
    assert pushed["series"]["H"]["p50"][:first] == pytest.approx(base["series"]["H"]["p50"][:first])


def test_custom_levers_keep_the_sc_check_of_their_stability_path(client):
    no_coup = client.post(
        "/simulate", json={"scenario": "no_coup", "levers": {"fdi_openness": 1.3}}
    ).json()
    actual = client.post("/simulate", json={"levers": {"fdi_openness": 1.3}}).json()

    gdp_check = next(c for c in no_coup["result"]["sc_checks"] if c["outcome"] == GDP)
    assert gdp_check["applicable"] is True  # same path as no coup over 2021-2024
    assert no_coup["result"]["gaps"] is not None
    actual_check = next(c for c in actual["result"]["sc_checks"] if c["outcome"] == GDP)
    assert actual_check["applicable"] is False
    assert actual["result"]["name"] == "custom"
    assert actual["credibility"]["credible"] is True


@pytest.mark.parametrize(
    "body",
    [
        {"scenario": "utopia"},
        {"levers": {"magic_wand": 1.0}},
        {"levers": {"fdi_openness": 9.0}},
        {"levers": {"education_spend": 0.1}},
        {"levers": {"fdi_openness": "lots"}},
        {"scenario": "no_coup", "unexpected": True},
    ],
)
def test_simulate_rejects_bad_input_with_422(client, body):
    response = client.post("/simulate", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]


# --------------------------------------------------------------------------- #
# Credibility passthrough
# --------------------------------------------------------------------------- #


def test_a_non_credible_model_flows_through_to_every_modeled_response(tmp_path):
    data_dir = _copy_release(tmp_path)
    _edit_bool(data_dir / "sd_metrics.csv", "scope", "overall", "credible", value=False)
    _edit_bool(data_dir / "sc_metrics.csv", "outcome", GDP, "credible", value=False)
    store = load_store(DataSource.PROCESSED, data_dir)

    with _client(store) as client:
        scenarios = client.get("/scenarios").json()
        simulated = client.post("/simulate", json={"scenario": "no_coup"}).json()
        counterfactual = client.get("/counterfactual").json()

    for payload in (scenarios, simulated):
        assert payload["credibility"]["credible"] is False
        assert payload["credibility"]["message"] == config.SD_NOT_CREDIBLE_MESSAGE
    gdp = next(o for o in counterfactual["outcomes"] if o["outcome"] == GDP)
    assert gdp["credibility"] == {
        "credible": False,
        "pre_rmse_share": pytest.approx(gdp["metrics"]["pre_rmse_share"]),
        "threshold": config.SC_CREDIBLE_PRE_RMSE_SHARE,
        "message": config.SC_NOT_CREDIBLE_MESSAGE,
    }
    check = next(c for c in simulated["result"]["sc_checks"] if c["outcome"] == GDP)
    assert check["sc_credible"] is False and check["deviation"] is None


# --------------------------------------------------------------------------- #
# Startup, settings and CORS
# --------------------------------------------------------------------------- #


def test_missing_data_fails_startup_clearly(tmp_path):
    with pytest.raises(DataUnavailableError, match="make models"):
        load_store(DataSource.PROCESSED, tmp_path)
    settings = Settings(DataSource.PROCESSED, tmp_path, ("http://localhost:5173",))
    with pytest.raises(DataUnavailableError), TestClient(create_app(settings=settings)):
        pass


def test_a_hand_edited_release_fails_its_manifest(tmp_path):
    data_dir = tmp_path / "release"
    shutil.copytree(RELEASE, data_dir)
    path = data_dir / f"{config.SC_WEIGHTS_STEM}.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("0.6", "0.7"), encoding="utf-8")

    with pytest.raises(DataUnavailableError, match="manifest"):
        load_store(DataSource.RELEASE, data_dir)


def test_settings_read_the_environment():
    settings = Settings.from_env(
        {"AMBER_DATA_SOURCE": "processed", "AMBER_CORS_ORIGINS": "https://a.app, https://b.app/"}
    )
    assert settings.data_source is DataSource.PROCESSED
    assert settings.data_dir == config.PROCESSED_DATA_DIR
    assert settings.cors_origins == ("https://a.app", "https://b.app")
    assert Settings.from_env({}).data_source is DataSource.RELEASE
    with pytest.raises(ValueError, match="AMBER_DATA_SOURCE"):
        Settings.from_env({"AMBER_DATA_SOURCE": "live"})


def test_cors_allows_only_the_configured_origins(store):
    with _client(store, origins=("https://amber.example",)) as client:
        allowed = client.get("/health", headers={"Origin": "https://amber.example"})
        denied = client.get("/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "https://amber.example"
    assert "access-control-allow-origin" not in denied.headers


# --------------------------------------------------------------------------- #
# Release snapshot
# --------------------------------------------------------------------------- #


def test_the_committed_release_matches_its_manifest_and_config(store):
    manifest = release.read_manifest(RELEASE)

    assert manifest is not None
    assert set(manifest.files) == {f"{stem}.csv" for stem in config.RELEASE_STEMS}
    assert len(store.nodes) == 3 ** len(sd.UNIDENTIFIED)
    assert store.nodes[0].central


def test_build_release_copies_hashes_and_normalizes_line_endings(tmp_path):
    source = tmp_path / "processed"
    source.mkdir()
    for stem in config.RELEASE_STEMS:
        text = (RELEASE / f"{stem}.csv").read_bytes().replace(b"\n", b"\r\n")
        (source / f"{stem}.csv").write_bytes(text)  # as pandas writes them on Windows
    (tmp_path / "release").mkdir()
    (tmp_path / "release" / "retired.csv").write_text("x\n", encoding="utf-8")

    manifest = release.build_release(source, tmp_path / "release")

    written = json.loads((tmp_path / "release" / config.RELEASE_MANIFEST).read_text("utf-8"))
    assert written["files"] == manifest.files
    assert not (tmp_path / "release" / "retired.csv").exists()
    for name, entry in manifest.files.items():
        body = (tmp_path / "release" / name).read_bytes()
        assert b"\r\n" not in body
        assert body == (RELEASE / name).read_bytes()
        assert entry["sha256"] == release._sha256(tmp_path / "release" / name)
    assert load_store(DataSource.RELEASE, tmp_path / "release").manifest is not None


def test_build_release_refuses_a_partial_build(tmp_path):
    with pytest.raises(FileNotFoundError, match="make models"):
        release.build_release(tmp_path, tmp_path / "release")
    assert not (tmp_path / "release").exists()

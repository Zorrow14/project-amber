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

from amber import config, historical, i18n, release
from amber.api.main import create_app
from amber.api.settings import Settings
from amber.api.store import DataStore, DataUnavailableError, load_store
from amber.config import DataSource
from amber.modeling import divergence as dv
from amber.modeling import synthetic_control as sc
from amber.modeling import system_dynamics as sd

RELEASE = config.RELEASE_DATA_DIR
GDP = config.GDP_PC_INDICATOR
FORBIDDEN = {
    sd: ("calibrate", "profile", "backtest"),
    sc: ("fit_synthetic_control", "run_placebo_space", "run_placebo_time", "leave_one_out", "run"),
    # The historical layer is served as-is: nothing recomputes a path on a request.
    dv: ("divergence_path", "comparator_growth"),
    historical: ("run_divergence", "sensitivity_metrics", "discover_coverage", "fetch_candidates"),
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
        assert payload["credibility"]["message_i18n"] == i18n.text(config.SD_NOT_CREDIBLE_MESSAGE)
    gdp = next(o for o in counterfactual["outcomes"] if o["outcome"] == GDP)
    assert gdp["credibility"] == {
        "credible": False,
        "pre_rmse_share": pytest.approx(gdp["metrics"]["pre_rmse_share"]),
        "threshold": config.SC_CREDIBLE_PRE_RMSE_SHARE,
        "message": config.SC_NOT_CREDIBLE_MESSAGE,
        "message_i18n": i18n.text(config.SC_NOT_CREDIBLE_MESSAGE),
    }
    check = next(c for c in simulated["result"]["sc_checks"] if c["outcome"] == GDP)
    assert check["sc_credible"] is False and check["deviation"] is None
    assert check["reason_i18n"] == i18n.text(config.SC_CHECK_NOT_CREDIBLE_MESSAGE)


# --------------------------------------------------------------------------- #
# Locales: every display string arrives in English and Burmese
# --------------------------------------------------------------------------- #


def _twins(node: object, path: str = "") -> Iterator[tuple[str, object, object]]:
    """Every ``x_i18n`` field in a payload, with its English sibling ``x``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key.endswith("_i18n"):
                yield f"{path}.{key}", node[key.removesuffix("_i18n")], value
            yield from _twins(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _twins(value, f"{path}[{i}]")


def _localized_payloads(client: TestClient) -> dict[str, object]:
    return {
        "/meta": client.get("/meta").json(),
        "/counterfactual": client.get("/counterfactual").json(),
        "/scenarios": client.get("/scenarios").json(),
        "/historical": client.get("/historical").json(),
        **{
            f"/historical/divergence?comparator={key}": client.get(
                "/historical/divergence", params={"comparator": key}
            ).json()
            for key in config.DIVERGENCE_COMPARATORS
        },
        "/index": client.get("/index").json(),
        "/simulate (custom)": client.post(
            "/simulate", json={"scenario": "no_coup", "levers": {"education_spend": 1.5}}
        ).json(),
    }


def test_every_display_string_carries_a_burmese_twin_that_matches_its_english(client):
    checked = 0
    for name, payload in _localized_payloads(client).items():
        for path, english, twin in _twins(payload):
            where = f"{name} {path}"
            if english is None:
                assert twin is None, where
                continue
            if isinstance(english, list):
                pairs = list(zip(english, twin, strict=True))
            elif isinstance(english, dict):  # framing: field -> text, field -> {en, my}
                assert set(english) == set(twin), where
                pairs = [(english[key], twin[key]) for key in english]
            else:
                pairs = [(english, twin)]
            for en, localized in pairs:
                assert set(localized) == set(i18n.LOCALES), where
                assert localized["en"] == en, where
                if en:
                    burmese = localized["my"]
                    assert burmese and burmese != en, where
                    assert i18n.is_unicode_burmese(burmese), where
                    assert not i18n._MYANMAR_DIGITS.search(burmese), where
                checked += 1
    # Countries, indicators, pillars, levers, scenarios, markers and caveats: ~150.
    assert checked > 100


def test_meta_names_its_locales_and_labels_every_entity_in_both(client):
    body = client.get("/meta").json()

    assert body["locales"] == ["en", "my"]
    assert body["default_locale"] == "en"
    assert body["translation_review_pending"] == len(i18n.REVIEW)
    assert {c["iso3"]: c["name_i18n"]["my"] for c in body["countries"]} == {
        iso3: i18n.MY[name] for iso3, name in config.COUNTRIES.items()
    }
    assert [s["label_i18n"]["my"] for s in body["scenarios"]] == [
        i18n.MY[s.label] for s in config.SCENARIOS
    ]
    assert body["framing_i18n"]["scenario"] == i18n.text(config.SCENARIO_FRAMING)
    historical_meta = body["historical"]
    assert historical_meta["framing_i18n"]["divergence"] == i18n.text(config.DIVERGENCE_FRAMING)
    assert [e["label_i18n"] for e in historical_meta["events"]] == [
        i18n.text(e.label) for e in config.HISTORICAL_EVENTS
    ]


def test_the_english_wording_is_unchanged_by_the_templates(client):
    simulated = client.post(
        "/simulate", json={"scenario": "no_coup", "levers": {"education_spend": 1.5}}
    ).json()["result"]
    assert simulated["label"] == "No coup, custom levers"
    assert (
        simulated["label_i18n"]["my"]
        == i18n.fill(config.CUSTOM_SCENARIO_LABEL, base=i18n.text("No coup"))["my"]
    )
    divergence = client.get("/historical/divergence").json()
    assert (
        divergence["notes"][0]
        == "The path starts at Myanmar's actual 1960 level, itself low reliability."
    )
    baseline = next(
        s
        for s in client.get("/scenarios").json()["scenarios"]
        if s["name"] == config.SD_BASELINE_SCENARIO
    )
    reasons = {c["reason"] for c in baseline["sc_checks"]}
    assert (
        "This scenario leaves the no-coup path before 2025, so the synthetic control is not "
        "its reference."
    ) in reasons


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
# Caching, compression, load-once and hermeticity
# --------------------------------------------------------------------------- #

PRECOMPUTED_GETS = ("/meta", "/counterfactual", "/scenarios", "/historical/divergence")
WEIGHTS = "economy=2,innovation=1,human_development=1"


@pytest.mark.parametrize("path", PRECOMPUTED_GETS)
def test_precomputed_gets_carry_an_etag_and_revalidate_to_304(client, path):
    first = client.get(path)
    etag = first.headers["etag"]

    assert first.status_code == 200
    assert etag.startswith('W/"')
    assert first.headers["cache-control"] == f"public, max-age={config.API_CACHE_MAX_AGE_SECONDS}"
    assert first.json()  # the pre-serialized body is still the full JSON payload

    revalidated = client.get(path, headers={"If-None-Match": etag})
    assert revalidated.status_code == 304
    assert revalidated.content == b""
    assert revalidated.headers["etag"] == etag

    stale = client.get(path, headers={"If-None-Match": 'W/"something-else"'})
    assert stale.status_code == 200


def test_query_gets_are_cacheable_but_errors_health_and_simulate_are_not(client):
    cache = f"public, max-age={config.API_CACHE_MAX_AGE_SECONDS}"
    assert client.get("/panel").headers["cache-control"] == cache
    assert client.get("/index", params={"weights": WEIGHTS}).headers["cache-control"] == cache
    assert client.get("/historical").headers["cache-control"] == cache

    bad = client.get("/index", params={"weights": "economy=-1"})
    assert bad.status_code == 422
    assert "max-age" not in bad.headers.get("cache-control", "")
    assert client.get("/health").headers["cache-control"] == "no-store"
    assert "max-age" not in client.post("/simulate", json={}).headers.get("cache-control", "")


def test_large_responses_are_gzipped(client):
    response = client.get("/scenarios", headers={"Accept-Encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    assert response.json()["scenarios"]


def test_the_snapshot_is_loaded_and_presented_once_per_process(monkeypatch):
    from amber.api import main

    calls = {"load": 0, "present": 0}
    real_load, real_present = main.load_store, main.build_precomputed

    def counting_load(*args: object, **kwargs: object) -> DataStore:
        calls["load"] += 1
        return real_load(*args, **kwargs)

    def counting_present(*args: object, **kwargs: object):
        calls["present"] += 1
        return real_present(*args, **kwargs)

    monkeypatch.setattr(main, "load_store", counting_load)
    monkeypatch.setattr(main, "build_precomputed", counting_present)
    settings = Settings(DataSource.RELEASE, RELEASE, ("http://localhost:5173",))
    with TestClient(create_app(settings=settings)) as client:
        for _ in range(3):
            for path in (*PRECOMPUTED_GETS, "/panel", "/index", "/historical", "/health"):
                assert client.get(path).status_code == 200
            assert client.post("/simulate", json={"levers": {"fdi_openness": 1.2}}).is_success

    assert calls == {"load": 1, "present": 1}


def test_the_api_serves_the_release_with_no_outbound_connections(monkeypatch):
    """A fresh clone's API needs nothing but data/release: no World Bank, no network."""
    import socket

    real_connect = socket.socket.connect
    loopback = {"127.0.0.1", "::1", "localhost"}

    def guarded_connect(self: socket.socket, address: object) -> None:
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and host not in loopback:
            msg = f"The API tried to open an outbound connection to {address!r}"
            raise AssertionError(msg)
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    with pytest.raises(AssertionError, match="outbound"):  # the guard is live
        socket.create_connection(("api.worldbank.org", 443), timeout=1)

    with TestClient(create_app(settings=Settings.from_env({}))) as client:
        assert client.get("/health").json()["data"]["source"] == "release"
        for path in (*PRECOMPUTED_GETS, "/panel", "/index", "/historical"):
            assert client.get(path).status_code == 200
        assert client.post("/simulate", json={"scenario": "no_coup"}).status_code == 200


# --------------------------------------------------------------------------- #
# Historical arc (phase 7)
# --------------------------------------------------------------------------- #

HISTORICAL_ROW = {"country_iso3", "indicator_id", "year", "value", "source", "reliability"}


def test_meta_carries_the_historical_settings_from_config(client):
    body = client.get("/meta").json()["historical"]

    assert body["window"] == {"start": config.HISTORICAL_START, "end": config.HISTORICAL_END}
    assert [c["iso3"] for c in body["countries"]] == list(config.HISTORICAL_COUNTRIES)
    roles = {c["iso3"]: c["role"] for c in body["countries"]}
    assert roles[config.TREATED_COUNTRY] == "treated"
    assert {iso3 for iso3, role in roles.items() if role == "comparator"} == set(
        config.HISTORICAL_COMPARATORS
    )
    assert [(e["year"], e["label"]) for e in body["events"]] == [
        (e.year, e.label) for e in config.HISTORICAL_EVENTS
    ]
    assert {c["key"] for c in body["comparators"]} == {
        s.comparator for s in config.DIVERGENCE_SCENARIOS
    }
    default = next(
        s for s in config.DIVERGENCE_SCENARIOS if s.name == config.DIVERGENCE_DEFAULT_SCENARIO
    )
    assert body["default_comparator"] == default.comparator
    assert body["divergence_anchor"] == default.anchor_year
    assert body["sensitivity_anchors"] == list(config.DIVERGENCE_SENSITIVITY_ANCHORS)
    assert body["reliability"] == [
        {"country_iso3": iso3, "standard_from": year}
        for iso3, year in config.RELIABILITY_LOW_BEFORE.items()
    ]
    sources = {i["id"]: i["source"] for i in body["indicators"]}
    assert sources[GDP] == "wb_constant"
    assert sources[config.MADDISON_INDICATOR] == "maddison"
    assert not any(i.endswith(config.CURRENT_USD_SUFFIX) for i in sources)
    framing = body["framing"]
    assert framing["divergence"] == config.DIVERGENCE_FRAMING
    assert framing["modeling_window"] == config.MODELING_WINDOW_MESSAGE
    assert framing["low_reliability"] == config.LOW_RELIABILITY_MESSAGE
    assert "counterfactual estimate" not in framing["divergence"].lower()


def test_historical_defaults_to_myanmar_and_the_comparator_on_gdp(client):
    body = client.get("/historical").json()

    assert body["countries"] == [
        config.TREATED_COUNTRY,
        *config.DIVERGENCE_COMPARATORS["THA"].units,
    ]
    assert body["indicators"] == [GDP, config.MADDISON_INDICATOR]
    assert {r["country_iso3"] for r in body["rows"]} == set(body["countries"])
    assert min(r["year"] for r in body["rows"]) == config.HISTORICAL_START
    assert all(set(r) == HISTORICAL_ROW for r in body["rows"])
    assert [e["year"] for e in body["events"]] == [e.year for e in config.HISTORICAL_EVENTS]
    assert body["modeling_window"]["start"] == config.MODELING_WINDOW_START
    assert config.LOW_RELIABILITY_MESSAGE in body["notes"]
    assert config.MODELING_WINDOW_MESSAGE in body["notes"]


def test_historical_rows_keep_their_source_and_reliability(client):
    rows = client.get("/historical?countries=MMR,THA,BGD").json()["rows"]
    cutoff = config.RELIABILITY_LOW_BEFORE[config.TREATED_COUNTRY]

    for row in rows:
        expected = "low" if row["country_iso3"] == "MMR" and row["year"] < cutoff else "standard"
        assert row["reliability"] == expected
    gdp = [r for r in rows if r["indicator_id"] == GDP]
    assert {r["source"] for r in gdp} == {"wb_constant"}
    assert any(r["reliability"] == "low" for r in rows)


def test_historical_serves_maddison_only_when_the_snapshot_has_it(client, store):
    has_maddison = (store.table(config.HISTORICAL_STEM)[config.COL_SOURCE] == "maddison").any()
    body = client.get("/historical?indicators=maddison.gdppc").json()

    assert bool(body["rows"]) == bool(has_maddison)
    assert all(r["source"] == "maddison" for r in body["rows"])
    present = {
        i["id"]: i["present"] for i in client.get("/meta").json()["historical"]["indicators"]
    }
    assert present[config.MADDISON_INDICATOR] == bool(has_maddison)


@pytest.mark.parametrize(
    "query",
    [
        "countries=ZZZ",
        "countries=",
        "indicators=NY.GDP.PCAP.CD",  # current US$ is never served
        "indicators=IT.NET.USER.ZS",  # did not extend back
        "indicators=MMR",
    ],
)
def test_historical_rejects_unknown_series_and_countries_with_422(client, query):
    response = client.get(f"/historical?{query}")
    assert response.status_code == 422
    assert "Unknown" in response.json()["detail"]


def test_divergence_carries_its_illustrative_flag_framing_and_sensitivity(client):
    body = client.get("/historical/divergence").json()

    assert body["scenario"] == config.DIVERGENCE_DEFAULT_SCENARIO
    assert body["comparator"] == "THA"
    assert body["scenario_illustrative"] is True
    assert body["framing"] == config.DIVERGENCE_FRAMING
    assert body["counterfactual_pointer"] == config.DIVERGENCE_POINTER_MESSAGE
    assert config.DIVERGENCE_NO_INFERENCE_MESSAGE in body["notes"]
    assert body["series"][0]["year"] == body["anchor_year"] == config.HISTORICAL_START
    assert body["series"][0]["path"] == pytest.approx(body["series"][0]["actual"])
    assert all(p["reliability"] in {"low", "standard"} for p in body["series"])
    assert {"anchor_year", "ratio_latest", "latest_year"} <= set(body["metrics"])
    banned = {"p_value", "pseudo_p_value", "credible", "credibility", "pre_rmse"}
    assert not banned & set(body) and not banned & set(body["metrics"])
    anchors = [s["anchor_year"] for s in body["sensitivity"]]
    assert set(config.DIVERGENCE_SENSITIVITY_ANCHORS) <= set(anchors)
    assert [s["anchor_year"] for s in body["sensitivity"] if s["default"]] == [body["anchor_year"]]


def test_divergence_serves_every_configured_comparator(client):
    for scenario in config.DIVERGENCE_SCENARIOS:
        body = client.get(f"/historical/divergence?comparator={scenario.comparator}").json()
        assert body["scenario"] == scenario.name
        assert body["scenario_illustrative"] is True


@pytest.mark.parametrize("comparator", ["USA", "", "track_thailand"])
def test_divergence_rejects_an_unknown_comparator_with_422(client, comparator):
    response = client.get(f"/historical/divergence?comparator={comparator}")
    assert response.status_code == 422
    assert "Unknown comparator" in response.json()["detail"]


def test_a_snapshot_with_a_non_illustrative_divergence_row_fails_startup(tmp_path):
    data = _copy_release(tmp_path)
    path = data / f"{config.HISTORICAL_DIVERGENCE_STEM}.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "scenario_illustrative"] = False
    frame.to_csv(path, index=False)

    with pytest.raises(DataUnavailableError, match="scenario_illustrative"):
        load_store(DataSource.PROCESSED, data)


def test_a_snapshot_without_reliability_fails_startup(tmp_path):
    data = _copy_release(tmp_path)
    path = data / f"{config.HISTORICAL_STEM}.csv"
    pd.read_csv(path).drop(columns=[config.COL_RELIABILITY]).to_csv(path, index=False)

    with pytest.raises(DataUnavailableError, match="reliability"):
        load_store(DataSource.PROCESSED, data)


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

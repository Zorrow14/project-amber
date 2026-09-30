# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install                              # venv (.venv) + pip install -e ".[dev]"
make panel                                # fetch (cached) → clean → data/processed
make refresh                              # same, re-pulling from the World Bank API
make index                                # development index → data/processed/index.csv + reports/figures/
make sc                                   # synthetic control → data/processed/sc_*.csv + reports/figures/sc_*
make sd                                   # system dynamics → data/processed/sd_*.csv + reports/figures/sd_*
make models                               # sc, then sd
make notebook                             # execute notebooks/ into build/ (needs pip install -e ".[notebook]")
make test                                 # pytest, fully offline
make lint                                 # ruff check + ruff format --check
make format                               # apply fixes
make api                                  # uvicorn on the stub API
```

`make` is not installed on every dev box here; the direct equivalents are `python scripts/build_panel.py [--refresh]`, `python scripts/build_index.py [--weights economy=2,innovation=1,human_development=1]`, `pytest`, `ruff check .`. Use the venv interpreter (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere).

Single test: `pytest tests/test_cleaning.py::test_interpolation_bridges_interior_gaps`. A whole file: `pytest tests/test_ingestion.py`.

**Tests must never hit the network.** Ingestion sits behind the `IndicatorSource` protocol precisely so a `FakeSource` (in `tests/conftest.py`) can stand in. Keep it that way — CI has no World Bank access.

## Current state

Phases 1-4 (data layer, reconstruction + index, synthetic-control counterfactual, system-dynamics scenarios) are complete and verified against real data. `amber.api` is the remaining stub (`/health` only); phase 5 exposes index, counterfactual and scenarios over it.

`Amber-Project-Plan.md` is the authoritative spec: methodology, architecture, phases, risks. `docs/myanmar-precoup-calibration-reference.md` is the modeling rationale — the empirical pre-coup trajectory, the civilian government's forward plans, and the calibration caveats behind the constants in `config.py`. Read both before designing anything non-trivial; the sections below are the parts that constrain day-to-day code.

## Layout

`src/amber/config.py` holds every constant that encodes a modeling decision — donor pool, treatment year, the 2011 window, indicator→pillar map, panel schema, output stems. Add constants there rather than inlining them; the point is that the assumptions are auditable in one place.

Data flows `ingestion.fetch_panel` → `cleaning.build_panel` → `cleaning.interpolate_panel` / `cleaning.build_coverage_report` → `pipeline.run`. `data/raw/` caches raw pulls as parquet with JSON provenance sidecars; `data/processed/` holds the output tables. Both are gitignored and regenerable.

Phase 2 reads `panel_interpolated.csv`: `modeling.index.normalize_indicators` → `compute_pillar_indices` → `compute_index` → `reconstruction.run`, which writes `index.csv` and calls `figures.render_all`. `reports/figures/*.png` **are committed** (unlike `data/processed/`) because the README embeds every one of them; regenerate them with `make index` whenever the index changes, and never leave one unreferenced. Chart captions are built from the run's actual normalization and weights - never hardcode "equal weights" or the scale into a caption. `figures.py` uses matplotlib's object API, never `pyplot`, so it needs no backend — keep it that way.

Phase 3 reads `panel_interpolated.csv` and `index.csv`: `synthetic_control.outcome_matrix` → `fit_synthetic_control` → `run_placebo_space` / `run_placebo_time` / `leave_one_out`, bundled per outcome by `synthetic_control.run`; `counterfactual.run` loops the configured outcomes, writes the six `sc_*` tables and calls `figures.render_counterfactual`. Fit settings travel together in one frozen `SCSettings`, so placebos and refits cannot diverge from the base fit.

Notebooks are walkthroughs only; logic belongs in `src/amber`. It is **committed without outputs** - `tests/test_notebooks.py` fails CI otherwise - because the charts already live in `reports/figures`. `make notebook` executes into the gitignored `build/`. Ruff lints and formats `.ipynb` too.

## What Amber is

Three modeling layers over one shared country-year panel, joined by a combined index:

| Layer | Question | Method |
|---|---|---|
| Past | What happened, 2011–present? | Real indicator series, cleaned into a tidy panel. Descriptive; also establishes the pre-treatment trend the counterfactual depends on. |
| Counterfactual | What if the Feb 2021 coup hadn't happened? | Synthetic control. A weighted blend of donor-pool countries fitted to real Myanmar pre-2021 on the outcome and predictors; post-2021 divergence is the estimate. |
| Future | What could still happen, to ~2035? | System dynamics (PySD): stocks for physical capital, human capital, infrastructure/connectivity and institutional stability, with a connectivity → productivity → investment → infrastructure feedback loop. |

## Modeling rules

These are decisions already made. Don't quietly re-litigate them in code.

- **Modeling window starts at 2011.** Data may be ingested from ~2000, but pre-2011 military-era statistics are unreliable and must be excluded from calibration.
- **Treatment point is February 2021.**
- **Donor pool:** regional peers such as Vietnam, Cambodia, Bangladesh, Laos, Nepal, Indonesia. Screen out any country with its own concurrent 2021+ shock — a contaminated donor breaks the estimate. The pool must be configurable, and pool sensitivity is a required robustness check.
- **Robustness is part of the counterfactual, not an extra:** placebo tests on untreated donors, plus varying the donor pool. Report pre-treatment fit error.
- **Index aggregation is geometric-mean style** across the three pillars (economy · innovation/tech · human development), so weakness in one pillar can't be masked by strength in another. Pillar weights are user controls — never hardcode them.
- **Outputs are estimates and scenarios, never forecasts.** Carry uncertainty through to the API and the UI wording.

## Index rules

- Polarity, the log-transform set, default weights and the [0.01, 1] clip all live in `config.py`; `_check_index_config()` fails at import if `INDICATOR_POLARITY` drifts out of step with `INDICATORS`. A new indicator needs an explicit polarity.
- **The index holds only `INDEX_INDICATORS`** - every panel indicator except `INDEX_EXCLUDED` (poverty, high-tech exports: kept in the panel as history, with reasons). The index must mean the same thing in history, the counterfactual and the projections, so it contains only what every layer can produce; `SD_INDICATOR_LINKS` must cover exactly `INDEX_INDICATORS`. Don't add an indicator to the index that the future model cannot produce, and don't hold one flat to fake it.
- Normalization defaults to **fixed goalposts** (`config.GOALPOSTS`), so history is stable and counterfactual/projected values land on the same ruler. Standards are used verbatim where they exist (HDI life expectancy 20-85; SDG Index under-5 mortality 2.6-130); the rest were seeded once with `index.seed_goalpost` (25% of span, clamped to natural domain, rounded outward) and **frozen**. Never recompute goalposts from data at runtime - that reintroduces the drift they exist to remove. Re-seed deliberately only when the indicator set changes, and record the source string. Pooled min-max survives as `method="pooled"` for comparison only.
- A value outside its goalposts is clipped and logged as a warning. If that warning fires on real data, a goalpost needs widening. Known limit: the income ceiling ($6,850) is reached by Vietnam around 2032 at ~6% growth.
- Pillars average over *observed* indicators, and `coverage` records the share. Movements where coverage changes are partly composition effects (Myanmar: enrollment stops after 2018, internet after 2020, health expenditure missing 2024 - six of nine by 2024). The charts ring every partial-coverage point — preserve that encoding.
- Combined coverage counts only indicators in positively-weighted pillars, so zero-weighting a pillar doesn't drag coverage down.
- A combined score requires every positively-weighted pillar. Don't relax this to "whatever pillars exist"; that reintroduces the masking the geometric mean prevents.

## Synthetic-control rules

- Weights are convex (non-negative, sum to 1), solved with seeded SLSQP restarts on z-scored pre-period outcome features, V = identity. Don't add nested V-optimisation or unconstrained regression weights: six donors can't support either, and the simplex is what stops extrapolation beyond the donor hull.
- **The p-value floor is 1/7** (Myanmar + six donors). Never describe a result as "significant at 5%"; say it ranks first of seven.
- Read `pre_rmse_share` before the gap. `SyntheticControlResult.credible` is true only when it is at most `SC_CREDIBLE_PRE_RMSE_SHARE` (10%); that one property drives both the chart captions and the `credible` column of `sc_metrics`, so the prose and the data cannot disagree. It is currently false for the combined index (pre-RMSE 24% of level), where Myanmar starts below every donor. A non-credible fit is not a weaker estimate but no estimate: never present its gap as an effect, and read any verdict from the property rather than re-deriving it.
- Report `n_weighted_donors` (weight >= `SC_WEIGHT_THRESHOLD`) beside `n_effective_donors` (1/sum(w^2)): the first is the conventional count, the second shows concentration.
- The fit window keeps 2020 (COVID is shared with donors), but Myanmar's WDI 2020 (fiscal Oct 2019-Sep 2020, pre-coup; WDI assigns a fiscal year to the calendar year holding most of its months) reads -9.1% against a contemporaneous World Bank estimate of +0.5%, and no donor blend reaches it. WDI 2021 includes four pre-coup months. Report the `--pre-period-end 2019` and `--rebase` variants alongside the default when quoting magnitudes.
- Placebos use the other donors only, never Myanmar. Placebos with pre-RMSE over `SC_PLACEBO_POOR_FIT_MULTIPLE` x Myanmar's are drawn faintly but still counted in the p-value.

## System-dynamics rules

- The engine is a hand-written numpy difference-equation simulator in `modeling/system_dynamics.py`, not PySD (a documented deviation from the plan). `dynamics.py` is the orchestration layer (inputs, tables, CLI) like `reconstruction.py`/`counterfactual.py`; the step function lives with the model.
- Scenarios, levers, parameters (value, bounds, calibrate flag) and indicator links are **data in config**; `_check_system_dynamics_config()` takes them as arguments so tests can feed it broken inputs. Scenario stability is a *recovery* path r in [0, 1] (S = S_post + r(1 - S_post)), so scenarios stay valid whatever calibration finds for S_post. Levers apply from `SD_PROJECTION_START`; stability paths can branch at the treatment year.
- Futures are scored through `modeling.index.compute_index` (goalposts), one pseudo-country per ensemble member - never a separate scoring path. The model produces exactly the index indicators, so projected and published scores share a composition. History still loses indicators Myanmar stopped reporting; the backtest scores the model over the same observed cells (`combined_matched`) for a like-for-like error, and reports the remaining step as `composition_gap` (sd_metrics, fan-chart footer). Never let a coverage step read as a scenario effect.
- `savings_rate` and `connectivity_tfp` (kappa, the leapfrog channel) are **unidentified** (`SDParameter.unidentified`): fixed in the central fit, but `profile()` refits history at every low/assumed/high combination and the ensemble cycles members through those nodes, so the bands carry the assumption. Every run re-checks flatness (`SD_PROFILE_TOLERANCE`, `sd_profile.flat`); a steep node means the parameter is identified and should be calibrated. Gamma (`stability_elasticity`) stays calibrated. Before freeing or fixing a parameter, profile it; a fitted value on a bound (`at_bound` in `sd_calibration` / `sd_profile`) means weak identification or a strained corner.
- Members share parameter draws across scenarios, so compare scenarios with the **paired** gap (`SimulationResult.gaps`, `sd_gaps`, `share_above`), not by whether marginal bands overlap. The live API must rebuild the ensemble from `sd_profile`, never refit.
- COVID is a persistent level loss (`covid_persistence` = 1), from the donors' trend shortfall, which never recovered. Do not import the donors' *widening* shortfall - that would tune toward the SC and make the phase 3 check circular.
- Gates: `credible` on the `overall` row of `sd_metrics` (backtest nRMSE <= `SD_CREDIBLE_NRMSE`) drives every caption; the no-coup/SC overlap deviation (vs `SD_SC_TOLERANCE`) is reported, never tuned away. Shares must use saturating links (see `LinkKind.BOUNDED`) - a power law compounds past its goalpost within the horizon.
- Framing is "scenario", never "forecast". Known misses: the model does not reproduce post-2021 stagnation (actual continuation is optimistic), and connectivity saturates by the mid-2020s because Myanmar's internet data stop in 2020.

## Data rules

- **One source per indicator, applied identically to every country.** Mixing vintages or fiscal- vs calendar-year conventions across sources is a defect, not a convenience. World Bank WDI is primary; IMF WEO is cross-check only; UNDP for HDI components; ACLED for conflict intensity.
- **Cache raw pulls unmodified**; every cleaning step is scripted so raw → panel is reproducible with no manual steps. Prefer APIs / structured providers over scraping.
- **Missing values are interpolated or explicitly flagged**, never silently dropped. Several Myanmar series go dark after 2020 — document these and use continuous proxies where sensible (e.g. mobile subscriptions for connectivity).

A known wrinkle: WDI's Myanmar GDP series sits on a **fiscal**-year basis, so it does not match the calendar-year IMF figures tabulated in the calibration reference (2020 reads −9.1% in WDI vs −1.2% in the IMF table). That divergence is expected and must not be "fixed" by splicing sources — internal consistency across countries is what the counterfactual needs. Note the basis wherever the series is presented.

## Stack

Installed: Python (3.11+ declared; the local venv runs 3.14 because the registered 3.13 is broken), pandas 3.x, numpy, pyarrow, wbgapi, matplotlib, scipy, FastAPI/uvicorn, pytest, ruff; plus the `notebook` extra (ipykernel, nbconvert).

Not installed and unused: the `modeling` extra (statsmodels, scikit-learn). PySD was dropped. The React/Recharts frontend (Vercel) and API deploy (Render) are phase 5–6.

## How to build it

Phase order is 0 setup → 1 data layer → 2 reconstruction + index → 3 counterfactual → 4 future model → 5 frontend → 6 polish & deploy. **Phases 1–4 are done; Phase 5 (API + frontend) is next.**

Against scope creep across three modeling layers, the plan prescribes a **vertical slice: take one pillar end-to-end first** rather than building each layer out horizontally.

## Framing

The README and plan both insist Amber is "an analytical instrument, not an argument". The 2021 coup is treated as a documented event with measurable consequences, with no partisan stance. Assumptions — donor pool, index weights, lever ranges — are surfaced as adjustable controls rather than baked in, and public-facing text stays neutral and factual.

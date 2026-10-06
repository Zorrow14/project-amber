# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **For reviewers:** this is the project's conventions file and the AI coding agent's working notes - the decisions the code must keep, in terse form. Start with the [README](README.md); the long-form rationale is in [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Commands

```bash
make install                              # venv (.venv) + pip install -e ".[dev]"
make panel                                # fetch (cached) → clean → data/processed
make refresh                              # same, re-pulling from the World Bank API
make index                                # development index → data/processed/index.csv + reports/figures/
make sc                                   # synthetic control → data/processed/sc_*.csv + reports/figures/sc_*
make sd                                   # system dynamics → data/processed/sd_*.csv + reports/figures/sd_*
make historical                           # 1960+ history + divergence → data/processed/historical*.csv + reports/figures/historical_*
make models                               # sc, sd, then historical
make release                              # copy the served tables into the committed data/release + manifest
make notebook                             # execute notebooks/ into build/ (needs pip install -e ".[notebook]")
make test                                 # pytest + the frontend typecheck and smoke test, fully offline
make test-backend                         # pytest only
make lint                                 # ruff check + ruff format --check, and eslint
make format                               # apply fixes
make api                                  # uvicorn on :8000 serving data/release (AMBER_DATA_SOURCE=processed for make models output)
make frontend-install / frontend-dev / frontend-build / frontend-test / frontend-preview
make smoke                                # CDP browser smoke test against frontend-preview (:4173) + api
```

Frontend commands run in `frontend/`: `npm ci`, `npm run dev`, `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `npm run smoke -- --url <app> [--screenshots ../docs/images] [--all]` (needs Chrome/Edge; the API must allow the app's origin via `AMBER_CORS_ORIGINS`).

`make` is not installed on every dev box here; the direct equivalents are `python scripts/build_panel.py [--refresh]`, `python scripts/build_index.py [--weights economy=2,innovation=1,human_development=1]`, `pytest`, `ruff check .`. Use the venv interpreter (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere).

Single test: `pytest tests/test_cleaning.py::test_interpolation_bridges_interior_gaps`. A whole file: `pytest tests/test_ingestion.py`.

**Tests must never hit the network.** Ingestion sits behind the `IndicatorSource` protocol precisely so a `FakeSource` (in `tests/conftest.py`) can stand in. Keep it that way — CI has no World Bank access.

## Current state

All six phases are complete (v1.0.0): data layer, reconstruction + index, synthetic-control counterfactual, system-dynamics scenarios, the API + React frontend, and the phase 6 polish (hardening, accessibility, docs, deploy runbook). Unreleased on top:
- the visual redesign and a motion layer;
- phase 7, a 1960+ historical layer with an illustrative divergence scenario, served precomputed by the API and drawn in the app's Historical arc view;
- English + Burmese i18n. The Burmese honesty strings await a Burmese speaker's review: `docs/i18n-review.md`;
- an About landing page, shareable URL state, CSV/PNG chart downloads, a share card and Sources & citations (presentation only). Not yet deployed or tagged - the user runs `DEPLOY.md`. Reader-facing long form lives in `docs/METHODOLOGY.md` and `docs/LIMITATIONS.md`; keep them in step with config when a modeling constant changes.

`docs/Amber-Project-Plan.md` is the authoritative spec: methodology, architecture, phases, risks. `docs/myanmar-precoup-calibration-reference.md` is the modeling rationale — the empirical pre-coup trajectory, the civilian government's forward plans, and the calibration caveats behind the constants in `config.py`. Read both before designing anything non-trivial; the sections below are the parts that constrain day-to-day code.

## Layout

`src/amber/config.py` holds every constant that encodes a modeling decision — donor pool, treatment year, the 2011 window, indicator→pillar map, panel schema, output stems. Add constants there rather than inlining them; the point is that the assumptions are auditable in one place.

Data flows `ingestion.fetch_panel` → `cleaning.build_panel` → `cleaning.interpolate_panel` / `cleaning.build_coverage_report` → `pipeline.run`. `data/raw/` caches raw pulls as parquet with JSON provenance sidecars; `data/processed/` holds the output tables. Both are gitignored and regenerable.

Phase 2 reads `panel_interpolated.csv`: `modeling.index.normalize_indicators` → `compute_pillar_indices` → `compute_index` → `reconstruction.run`, which writes `index.csv` and calls `figures.render_all`. `reports/figures/*.png` **are committed** (unlike `data/processed/`) because the README embeds every one of them; regenerate them with `make index` whenever the index changes, and never leave one unreferenced. Chart captions are built from the run's actual normalization and weights - never hardcode "equal weights" or the scale into a caption. `figures.py` uses matplotlib's object API, never `pyplot`, so it needs no backend — keep it that way.

Phase 3 reads `panel_interpolated.csv` and `index.csv`: `synthetic_control.outcome_matrix` → `fit_synthetic_control` → `run_placebo_space` / `run_placebo_time` / `leave_one_out`, bundled per outcome by `synthetic_control.run`; `counterfactual.run` loops the configured outcomes, writes the six `sc_*` tables and calls `figures.render_counterfactual`. Fit settings travel together in one frozen `SCSettings`, so placebos and refits cannot diverge from the base fit.

Phase 5: `amber.release` copies `config.RELEASE_STEMS` from `data/processed` into the **committed** `data/release/` with a `manifest.json` (sha256 per file, LF-normalized; `.gitattributes` marks it `-text`). `amber.api` (`main.create_app` -> routers `meta`, `panel`, `index`, `counterfactual`, `scenarios`) loads it once at startup (`store.load_store`, which checks hashes and config agreement), builds the static responses once (`deps.Precomputed`), and serializes through `presenters` into `schemas`. `frontend/` is Vite + React + TS + Recharts, driven entirely by `GET /meta`.

Phase 7 is self-contained: `historical.candidate_series` → `fetch_candidates` (via `ingestion.fetch_series`, same cache) → `discover_coverage` → `build_historical` + `load_maddison` → `combine` → `run_divergence` (`modeling/divergence.py`) / `sensitivity_metrics` → `figures.render_historical`. Nothing in phases 1-6 reads its tables. Four of them are in `RELEASE_STEMS` (spelled as literals there; `_check_historical_config` asserts they match) and are served precomputed by `api/routers/historical.py` (`/historical`, `/historical/divergence`, one cached body per comparator); the frontend's `views/History.tsx` draws them.

Notebooks are walkthroughs only; logic belongs in `src/amber`. It is **committed without outputs** - `tests/test_notebooks.py` fails CI otherwise - because the charts already live in `reports/figures`. `make notebook` executes into the gitignored `build/`. Ruff lints and formats `.ipynb` too.

## What Amber is

Three modeling layers over one shared country-year panel, joined by a combined index:

| Layer | Question | Method |
|---|---|---|
| Past | What happened, 2011–present? | Real indicator series, cleaned into a tidy panel. Descriptive; also establishes the pre-treatment trend the counterfactual depends on. |
| Counterfactual | What if the Feb 2021 coup hadn't happened? | Synthetic control. A weighted blend of donor-pool countries fitted to real Myanmar pre-2021 on the outcome and predictors; post-2021 divergence is the estimate. |
| Future | What could still happen, to ~2035? | System dynamics (hand-written numpy simulator): stocks for physical capital, human capital, infrastructure/connectivity and institutional stability, with a connectivity → productivity → investment → infrastructure feedback loop. |

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

## Historical-layer rules

- **Descriptive, plus one illustration; never a second causal estimate.** "Counterfactual estimate" is reserved for the phase 3 synthetic control; the historical layer says "illustrative scenario / divergence". The combined index stays 2011+ - never compute it back, and never NaN-fill or fabricate an indicator to make that possible.
- **Coverage is discovered, not assumed:** a series extends only with >= `HISTORICAL_MIN_OBSERVATIONS` *non-zero* treated-country observations before 2000 (WDI's pre-technology zeros are placeholders). The decision is written to `historical_coverage` every run.
- **Three rulers, never spliced.** WDI constant US$ (`wb_constant`) is the spine. Current-US$ series - and FDI % of GDP, whose denominator is current-US$ GDP - are in `HISTORICAL_RULER_EXCLUDED`, never fetched, and refused by a `.CD` guard. Maddison (`maddison.gdppc`, `maddison` tag) is pre-1960 only, never shares an id or a year with WDI, and is drawn on its own axis. `combine` fails if a series carries two sources.
- **Reliability:** `RELIABILITY_LOW_BEFORE` (Myanmar < 1990 = `low`) applies per country-year to every source; charts hatch those years and draw the line dotted. It is a data-quality flag, separate from the 2011 modeling-window *scope* boundary, which gets its own cue (a thin capped bracket, `MODELING_WINDOW_MESSAGE`). Never move the reliability cutoff to 2011 or merge the two cues. Keep both cues wherever historical data renders.
- **Divergence** = anchor level grown at the comparator's mean log growth (units observed in both years; gaps stop the path, never bridged). Every row carries `scenario_illustrative`; never add a p-value, fit or credibility column. The result turns on the anchor (1.25x from 1960, 0.37-0.49x from 1988+), so `DIVERGENCE_SENSITIVITY_ANCHORS` is always tabulated and stated on the chart - never quote one anchor alone. Thailand is not a no-coup country; don't label the path "no coups".

## API and frontend rules

- **The precompute/live boundary is load-bearing.** Only `/index` (`compute_index`) and `/simulate` (`run_scenarios` on the calibration and profile nodes rebuilt from `sd_calibration`/`sd_profile`) compute on request, both in `api/live.py`. Never call `calibrate`, `profile`, `backtest`, any synthetic-control fit, or any historical computation (`run_divergence`, `divergence_path`, coverage discovery) from the API; `tests/test_api.py` replaces them with functions that fail.
- **Caveats travel with the data.** Every modeled payload carries its verdict (`coverage`, `credibility`, `sc_checks`), and the UI renders it wherever the series appears: hollow points for coverage < 1, the not-credible banner and an "illustrative" badge (no gap stated as an effect) for `credible == false`, persistent "scenarios, not forecasts". A chart that hides its caveat is a defect. `Counterfactual.test.tsx` guards the banner.
- **The frontend hardcodes nothing** that config knows: countries, indicators, pillars, weights, levers, scenarios, thresholds and caveat wording all come from `/meta` (framing strings live in `config.py`). Every color, size, space, radius and motion value is a token in `styles/tokens.css` (light + dark; chart geometry Recharts needs as numbers in `lib/chartTokens.ts`) - no hex or px in components. The treated country is always `--data-hero`; donors take `--data-1..6` in meta order (`countryColors`). The data palette, the amber UI accent and the honesty tones are separate and validated - see `docs/design-system.md` before changing any of them.
- **`data/release/` is regenerated with `make release`, never edited** - the store refuses a snapshot that fails its manifest. The API tests run against it, so re-release after any model change and rerun `pytest`.
- `/simulate` levers override a named scenario (default: the baseline); the phase 3 check is reported only where a scenario follows the no-coup stability path through the overlap.
- **Motion follows the data and never gates a caveat.** Every Recharts series animates through `drawProps(useMotion())` (`lib/motion.ts`), never a hand-set `isAnimationActive`. Under `prefers-reduced-motion` nothing animates and the final state renders at once (`useReducedMotion`; `components/motion.test.tsx` guards it). Dots render only after a Recharts animation, so caveat dots (coverage rings) go on a separate static `Line`. Never animate opacity on a view, banner or caveat, or animate the hatching or window bracket. Fill a counterfactual gap only when `credible`. Scrubber tweens (`MOTION.stepTween`) must stay well under `MOTION.step`, so no year's label shows another year's value.
- **Two languages, English (default) and Burmese; Python stays English.**
  - **Where strings live.** Every UI string is a key in `frontend/src/i18n/locales/en.json`, with a twin in `my.json`. The keys are typed from `en.json`, and `i18n.test.tsx` checks key and placeholder parity. Never put a user-visible string in a component.
  - **API strings.** Every display string the API sends gets an `x_i18n: {en, my}` twin from `amber.i18n.MY`. That map is keyed by the English verbatim, so an edited English caveat fails startup until it is re-translated. Entity names are twinned too, so `localize` (run by `useApi`) puts every display field in the active language. A new display string needs its twin in both the schema and `MY`; `test_every_display_string_carries_a_burmese_twin_that_matches_its_english` catches a miss.
  - **Review flags.** Honesty strings, and labels for political events, are flagged for human review: `my.json` `_review`, and `i18n.REVIEW`. Never clear a flag without a Burmese speaker's sign-off (`docs/i18n-review.md`). A new or edited caveat gets re-flagged.
  - **Numerals stay Western in both languages.** Format numbers with `lib/format.ts`, which is pinned to `en-US`, never with `toLocaleString()`, because the `my` locale emits Myanmar digits. Ordinals and lists go through `i18n/words.ts`.
  - **Burmese type.** Unicode only, never Zawgyi; both label maps are checked. Burmese renders in Noto Sans Myanmar, after Inter in `--font-sans`. Its leading and tracking come from the `:root[lang="my"]` tokens. Never set a raw `line-height` or `letter-spacing` that would override them.
  - **The language choice** is React state only. `<html lang>` always names the language on screen.
- No localStorage/sessionStorage. **The URL query is the shareable state.**
  - **The modules.** `lib/url.ts` defines the schema: `view`, each view's `VIEW_PARAMS`, and `lang`. `context/route.tsx` applies it.
  - **Navigation and controls.** Opening a view pushes a history entry; a control change rewrites the current entry with `replaceState`.
  - **Reading and writing state.**
    - A view seeds its state from `useRoute().params`, checked against `/meta` (unknown falls back, out-of-range clamps).
    - It writes back through `useUrlState({...all its params})`, with `undefined` for any value at its default.
    - Write only values that differ from their defaults, and write them exactly, so a reload rebuilds the same state.
  - **Old links.** Legacy `#/view` links still open. Link between views with `Link`, never a raw `href`.
- **About is the landing page** (`DEFAULT_VIEW`; `VITE_DEFAULT_VIEW=overview` reverts it).
  - It renders before `/meta` answers (`MetaProvider bootless`), so never give it a `useMeta()`.
  - Its copy is the `views.about.*` keys, all flagged for review (table C of `docs/i18n-review.md`, with intent notes). In Burmese, each honesty passage shows a draft note while flagged.
- **Every `ChartFrame` offers CSV and PNG downloads** (`lib/export.ts`, lazy-loaded).
  - **What the files carry.** Both read the frame's title, caveat badge, callout, notes and source, so the caveat travels with the file. Give each frame an ASCII `exportName`, and give custom tables a raw `data` block (`seriesTable` adds one, with coverage columns).
  - **How the PNG draws text.** The canvas draws the SVG's text itself, because an SVG-as-image paints web-font text late or not at all. Don't go back to embedding fonts.
- **The share card** (Open Graph/Twitter in `index.html`).
  - Its description is the opening of `config.PROJECT_FRAMING`, checked by `tests/test_share_card.py`, so edit both together.
  - Its image is the static `public/og-image.png`; recapture it with `npm run smoke -- --og public/og-image.png`. Absolute URLs come from `VITE_SITE_URL`.
- **Sources & citations** (`lib/sources.ts`, `/#sources`) mirrors the README's "Data and attribution". Keep the two in step, and credit no source with more than it does. Citations stay in their published English form.
- Vitest pre-bundles Recharts (`deps.optimizer`) - without it the import alone takes ~20 s and the worker times out.
- **Every fetch goes through `useApi` + `<Async>`** (`components/LoadState.tsx`): transient failures (network, timeout, 502/503/504) retry with back-off for `WAKE_BUDGET_MS` showing the "waking the server" state - the Render free tier cold-starts in up to a minute - while a 422 is never retried and is explained. Data already on screen stays while a refresh runs or fails. Don't hand-roll loading/error JSX in a view.
- **`ChartFrame` requires a `summary`** (screen-reader text) and takes a `table` (`lib/describe.ts` builds both from the rows the chart draws). Its `badge` is a caveat and always shows; transient state goes in `status`, never in `badge`; coverage pills go in its `callout` slot. Charts build from the shared grammar in `charts/common.tsx` (axes, grid, tooltip, treatment line), direct end labels via `EndLabels`, and one `ChartTooltip`. Lines are distinguished by width, dash and end label as well as color; at phone width (`useChartLayout`) end labels drop and identity falls to the legend and patterns.
- The API's precomputed GETs are serialized once at startup and served with a weak ETag (`api/caching.py`); `/panel` and `/index` get `Cache-Control` only; `/health` is `no-store`. A change to a response's shape changes its bytes, so the ETag follows automatically.

## Data rules

- **One source per indicator, applied identically to every country.** Mixing vintages or fiscal- vs calendar-year conventions across sources is a defect, not a convenience. World Bank WDI is primary; IMF WEO is cross-check only; UNDP for HDI components; ACLED for conflict intensity.
- **Cache raw pulls unmodified**; every cleaning step is scripted so raw → panel is reproducible with no manual steps. Prefer APIs / structured providers over scraping.
- **Missing values are interpolated or explicitly flagged**, never silently dropped. Several Myanmar series go dark after 2020 — document these and use continuous proxies where sensible (e.g. mobile subscriptions for connectivity).

A known wrinkle: WDI's Myanmar GDP series sits on a **fiscal**-year basis, so it does not match the calendar-year IMF figures tabulated in the calibration reference (2020 reads −9.1% in WDI vs −1.2% in the IMF table). That divergence is expected and must not be "fixed" by splicing sources — internal consistency across countries is what the counterfactual needs. Note the basis wherever the series is presented.

## Stack

Installed: Python (3.11+ declared; the local venv runs 3.14 because the registered 3.13 is broken), pandas 3.x, numpy, pyarrow, wbgapi, matplotlib, scipy, FastAPI/uvicorn, pytest, ruff, httpx2 (TestClient); plus the `notebook` extra (ipykernel, nbconvert). Frontend (Node 22+): React 19, Recharts 3, Vite 8, TypeScript 6 (strict), Vitest 5 + Testing Library, ESLint 10.

Not installed and unused: the `modeling` extra (statsmodels, scikit-learn). PySD was dropped. Deploy targets: API on Render (`render.yaml`), frontend on Vercel (`frontend/vercel.json`, root directory `frontend`).

## How to build it

Phase order is 0 setup → 1 data layer → 2 reconstruction + index → 3 counterfactual → 4 future model → 5 frontend → 6 polish & deploy. **All phases are done (v1.0.0);** further work is the user's deploy (`DEPLOY.md`) and any post-1.0 extension, recorded in `CHANGELOG.md`.

Against scope creep across three modeling layers, the plan prescribes a **vertical slice: take one pillar end-to-end first** rather than building each layer out horizontally.

## Framing

The README and plan both insist Amber is "an analytical instrument, not an argument". The 2021 coup is treated as a documented event with measurable consequences, with no partisan stance. Assumptions — donor pool, index weights, lever ranges — are surfaced as adjustable controls rather than baked in, and public-facing text stays neutral and factual.

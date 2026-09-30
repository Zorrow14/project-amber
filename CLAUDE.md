# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install                              # venv (.venv) + pip install -e ".[dev]"
make panel                                # fetch (cached) → clean → data/processed
make refresh                              # same, re-pulling from the World Bank API
make index                                # development index → data/processed/index.csv + reports/figures/
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

Phases 1 (data layer) and 2 (reconstruction + index) are complete and verified against real data. Still deliberate stubs raising `NotImplementedError`: `amber.modeling.synthetic_control`, `amber.modeling.system_dynamics`, and `amber.api` (which serves `/health` only; index exposure is deferred to phase 5).

`Amber-Project-Plan.md` is the authoritative spec: methodology, architecture, phases, risks. `docs/myanmar-precoup-calibration-reference.md` is the modeling rationale — the empirical pre-coup trajectory, the civilian government's forward plans, and the calibration caveats behind the constants in `config.py`. Read both before designing anything non-trivial; the sections below are the parts that constrain day-to-day code.

## Layout

`src/amber/config.py` holds every constant that encodes a modeling decision — donor pool, treatment year, the 2011 window, indicator→pillar map, panel schema, output stems. Add constants there rather than inlining them; the point is that the assumptions are auditable in one place.

Data flows `ingestion.fetch_panel` → `cleaning.build_panel` → `cleaning.interpolate_panel` / `cleaning.build_coverage_report` → `pipeline.run`. `data/raw/` caches raw pulls as parquet with JSON provenance sidecars; `data/processed/` holds the output tables. Both are gitignored and regenerable.

Phase 2 reads `panel_interpolated.csv`: `modeling.index.normalize_indicators` → `compute_pillar_indices` → `compute_index` → `reconstruction.run`, which writes `index.csv` and calls `figures.render_all`. `reports/figures/*.png` **are committed** (unlike `data/processed/`) because the README embeds all three; regenerate them with `make index` whenever the index changes, and never leave one unreferenced. Chart captions are built from the run's actual normalization and weights - never hardcode "equal weights" or the scale into a caption. `figures.py` uses matplotlib's object API, never `pyplot`, so it needs no backend — keep it that way.

The notebook is a walkthrough only; logic belongs in `src/amber`. It is **committed without outputs** - `tests/test_notebooks.py` fails CI otherwise - because the charts already live in `reports/figures`. `make notebook` executes into the gitignored `build/`. Ruff lints and formats `.ipynb` too.

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
- Normalization defaults to **fixed goalposts** (`config.GOALPOSTS`), so history is stable and counterfactual/projected values land on the same ruler. Standards are used verbatim where they exist (HDI life expectancy 20-85; SDG Index under-5 mortality 2.6-130); the rest were seeded once with `index.seed_goalpost` (25% of span, clamped to natural domain, rounded outward) and **frozen**. Never recompute goalposts from data at runtime - that reintroduces the drift they exist to remove. Re-seed deliberately only when the indicator set changes, and record the source string. Pooled min-max survives as `method="pooled"` for comparison only.
- A value outside its goalposts is clipped and logged as a warning. If that warning fires on real data, a goalpost needs widening. Known limit: the income ceiling ($6,850) is reached by Vietnam around 2032 at ~6% growth.
- Pillars average over *observed* indicators, and `coverage` records the share. Movements where coverage changes are partly composition effects (Myanmar poverty exists only 2015–2017; internet stops after 2020). The charts ring every partial-coverage point — preserve that encoding.
- Combined coverage counts only indicators in positively-weighted pillars, so zero-weighting a pillar doesn't drag coverage down.
- A combined score requires every positively-weighted pillar. Don't relax this to "whatever pillars exist"; that reintroduces the masking the geometric mean prevents.

## Data rules

- **One source per indicator, applied identically to every country.** Mixing vintages or fiscal- vs calendar-year conventions across sources is a defect, not a convenience. World Bank WDI is primary; IMF WEO is cross-check only; UNDP for HDI components; ACLED for conflict intensity.
- **Cache raw pulls unmodified**; every cleaning step is scripted so raw → panel is reproducible with no manual steps. Prefer APIs / structured providers over scraping.
- **Missing values are interpolated or explicitly flagged**, never silently dropped. Several Myanmar series go dark after 2020 — document these and use continuous proxies where sensible (e.g. mobile subscriptions for connectivity).

A known wrinkle: WDI's Myanmar GDP series sits on a **fiscal**-year basis, so it does not match the calendar-year IMF figures tabulated in the calibration reference (2020 reads −9.1% in WDI vs −1.2% in the IMF table). That divergence is expected and must not be "fixed" by splicing sources — internal consistency across countries is what the counterfactual needs. Note the basis wherever the series is presented.

## Stack

Installed: Python (3.11+ declared; the local venv runs 3.14 because the registered 3.13 is broken), pandas 3.x, pyarrow, wbgapi, matplotlib, FastAPI/uvicorn, pytest, ruff; plus the `notebook` extra (ipykernel, nbconvert).

Not yet installed — declared in the `modeling` extra for later phases: statsmodels, scikit-learn, PySD. The React/Recharts frontend (Vercel) and API deploy (Render) are phase 5–6.

## How to build it

Phase order is 0 setup → 1 data layer → 2 reconstruction + index → 3 counterfactual → 4 future model → 5 frontend → 6 polish & deploy. **Phases 1–2 are done; Phase 3 (synthetic control) is next.**

Against scope creep across three modeling layers, the plan prescribes a **vertical slice: take one pillar end-to-end first** rather than building each layer out horizontally.

## Framing

The README and plan both insist Amber is "an analytical instrument, not an argument". The 2021 coup is treated as a documented event with measurable consequences, with no partisan stance. Assumptions — donor pool, index weights, lever ranges — are surfaced as adjustable controls rather than baked in, and public-facing text stays neutral and factual.

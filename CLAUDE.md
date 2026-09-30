# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install                              # venv (.venv) + pip install -e ".[dev]"
make panel                                # fetch (cached) → clean → data/processed
make refresh                              # same, re-pulling from the World Bank API
make test                                 # pytest, fully offline
make lint                                 # ruff check + ruff format --check
make format                               # apply fixes
make api                                  # uvicorn on the stub API
```

`make` is not installed on every dev box here; the direct equivalents are `python scripts/build_panel.py [--refresh]`, `pytest`, `ruff check .`. Use the venv interpreter (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere).

Single test: `pytest tests/test_cleaning.py::test_interpolation_bridges_interior_gaps`. A whole file: `pytest tests/test_ingestion.py`.

**Tests must never hit the network.** Ingestion sits behind the `IndicatorSource` protocol precisely so a `FakeSource` (in `tests/conftest.py`) can stand in. Keep it that way — CI has no World Bank access.

## Current state

Phase 1 (the data layer) is complete and verified against the live API: `amber.config`, `amber.ingestion`, `amber.cleaning`, `amber.pipeline`. Everything downstream is a deliberate stub that raises `NotImplementedError` — `amber.modeling.{index,synthetic_control,system_dynamics}` and `amber.api` (which serves `/health` only).

`Amber-Project-Plan.md` is the authoritative spec: methodology, architecture, phases, risks. `docs/myanmar-precoup-calibration-reference.md` is the modeling rationale — the empirical pre-coup trajectory, the civilian government's forward plans, and the calibration caveats behind the constants in `config.py`. Read both before designing anything non-trivial; the sections below are the parts that constrain day-to-day code.

## Layout

`src/amber/config.py` holds every constant that encodes a modeling decision — donor pool, treatment year, the 2011 window, indicator→pillar map, panel schema, output stems. Add constants there rather than inlining them; the point is that the assumptions are auditable in one place.

Data flows `ingestion.fetch_panel` → `cleaning.build_panel` → `cleaning.interpolate_panel` / `cleaning.build_coverage_report` → `pipeline.run`. `data/raw/` caches raw pulls as parquet with JSON provenance sidecars; `data/processed/` holds the three output tables. Both are gitignored and regenerable.

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

## Data rules

- **One source per indicator, applied identically to every country.** Mixing vintages or fiscal- vs calendar-year conventions across sources is a defect, not a convenience. World Bank WDI is primary; IMF WEO is cross-check only; UNDP for HDI components; ACLED for conflict intensity.
- **Cache raw pulls unmodified**; every cleaning step is scripted so raw → panel is reproducible with no manual steps. Prefer APIs / structured providers over scraping.
- **Missing values are interpolated or explicitly flagged**, never silently dropped. Several Myanmar series go dark after 2020 — document these and use continuous proxies where sensible (e.g. mobile subscriptions for connectivity).

A known wrinkle: WDI's Myanmar GDP series sits on a **fiscal**-year basis, so it does not match the calendar-year IMF figures tabulated in the calibration reference (2020 reads −9.1% in WDI vs −1.2% in the IMF table). That divergence is expected and must not be "fixed" by splicing sources — internal consistency across countries is what the counterfactual needs. Note the basis wherever the series is presented.

## Stack

Installed: Python (3.11+ declared; the local venv runs 3.14 because the registered 3.13 is broken), pandas 3.x, pyarrow, wbgapi, FastAPI/uvicorn, pytest, ruff.

Not yet installed — declared in the `modeling` extra for later phases: statsmodels, scikit-learn, PySD. The React/Recharts frontend (Vercel) and API deploy (Render) are phase 5–6.

## How to build it

Phase order is 0 setup → 1 data layer → 2 reconstruction + index → 3 counterfactual → 4 future model → 5 frontend → 6 polish & deploy. **Phase 1 is done; Phase 2 is next.**

Against scope creep across three modeling layers, the plan prescribes a **vertical slice: take one pillar end-to-end first** rather than building each layer out horizontally.

## Framing

The README and plan both insist Amber is "an analytical instrument, not an argument". The 2021 coup is treated as a documented event with measurable consequences, with no partisan stance. Assumptions — donor pool, index weights, lever ranges — are surfaced as adjustable controls rather than baked in, and public-facing text stays neutral and factual.

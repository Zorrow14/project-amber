# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The repository holds only `README.md`, `Amber-Project-Plan.md` and this file — no code, no package manifests, no CI. There are therefore no build, lint or test commands yet. Add them here as Phase 0 scaffolding lands, including how to run a single test.

`Amber-Project-Plan.md` is the authoritative spec: methodology, architecture, phases, risks. Read it before designing anything non-trivial; the sections below are the parts that constrain day-to-day code.

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

## Planned stack

Python · FastAPI backend (Render) · pandas with a SQLite/parquet cache · statsmodels / scikit-learn plus a synthetic-control library · PySD · React with Recharts / Plotly frontend (Vercel) · pytest · GitHub Actions.

## How to build it

Phase order is 0 setup → 1 data layer → 2 reconstruction + index → 3 counterfactual → 4 future model → 5 frontend → 6 polish & deploy. **Currently at Phase 1, the data layer.**

Against scope creep across three modeling layers, the plan prescribes a **vertical slice: take one pillar end-to-end first** rather than building each layer out horizontally.

## Framing

The README and plan both insist Amber is "an analytical instrument, not an argument". The 2021 coup is treated as a documented event with measurable consequences, with no partisan stance. Assumptions — donor pool, index weights, lever ranges — are surfaced as adjustable controls rather than baked in, and public-facing text stays neutral and factual.

# Amber

> A simulation of Myanmar's development — past, present, and the future that almost was.

*Amber* has two meanings baked into the name. It's the colour of **Suvarnabhumi**, the "Golden Land" — Myanmar's old name. And amber is the substance that freezes a single moment in time forever — here, the moment in 2021 where one timeline broke away from another. This project is an attempt to look at both timelines side by side.

---

## What is this?

Amber models Myanmar's development across three questions:

- **Where has it been?** — a reconstruction of the real trajectory from the 2011 reform era onward, built from actual economic and social indicators.
- **Where could it have been?** — a *counterfactual* estimate of how Myanmar might have developed had the 2021 coup not interrupted the democratic transition, using the [synthetic control method](https://en.wikipedia.org/wiki/Synthetic_control_method).
- **Where might it go?** — an interactive system-dynamics model where you can adjust levers (stability, investment openness, education spending, connectivity) and watch alternative futures unfold.

The counterfactual is the heart of it: a **synthetic Myanmar** is assembled from a weighted blend of comparable countries that *didn't* rupture in 2021 (Vietnam, Cambodia, and others), calibrated to match real Myanmar before the coup. The gap that opens up afterward is the estimate of what was lost.

This is an analytical tool, not an argument. It's built to make its assumptions visible and adjustable, so the data and the choices — not a predetermined conclusion — drive what you see.

---

## Approach

| Layer | Question | Method |
|-------|----------|--------|
| **Past** | What actually happened? | Real indicator series (World Bank / IMF), 2011–present |
| **Counterfactual** | What if there'd been no coup? | Synthetic control against a donor pool of peer economies |
| **Future** | What could still happen? | System-dynamics model with user-adjustable levers |

A user-adjustable **combined development index** (economy · innovation/tech · human development) ties the layers together, with the pillar weights exposed as controls — so "how you define development" becomes a setting, not an assumption.

---

## Tech stack

- **Backend:** Python · FastAPI
- **Modeling:** pandas · statsmodels / scikit-learn · PySD (system dynamics)
- **Frontend:** React · Recharts / Plotly (scenario charts + sliders)
- **Deploy:** Vercel (frontend) · Render (API)

## Data sources

- **World Bank WDI** — GDP, FDI, poverty, connectivity, health, education
- **IMF WEO** — growth, inflation, debt (cross-check)
- **UNDP** — HDI components
- **ACLED** — conflict intensity (for the post-2021 divergence)

Reference targets for the counterfactual come from the civilian government's own forward plans — the **2016 Economic Policy** and the **Myanmar Sustainable Development Plan (2018–2030)**.

---

## Data layer

The pipeline pulls 11 indicators across 7 countries (Myanmar plus the donor pool) for 2000–2024 from the World Bank WDI, caches every raw pull, and writes a tidy country-year panel.

```bash
make install      # venv + dependencies
make panel        # fetch (cached) → clean → write
make refresh      # same, but re-pull everything from the API
make test         # offline test suite
make lint         # ruff check + format check
```

Without `make`, the same steps are `python -m venv .venv`, `pip install -e ".[dev]"`, then `python scripts/build_panel.py [--refresh]`, `pytest`, `ruff check .`.

**Outputs** land in `data/processed/` (gitignored — always regenerable), each as both `.csv` and `.parquet`:

| File | Contents |
|---|---|
| `panel` | The tidy panel: `indicator_id, indicator_name, pillar, country_iso3, country_name, year, value, pre_2011`. Missing values stay `NaN`. |
| `panel_interpolated` | The same panel with **interior** gaps bridged linearly within each country-indicator series, plus an `imputed` flag. Nothing is extrapolated past the last real observation. |
| `coverage_report` | Observation counts per country × indicator, with `is_dark` marking series that stop reporting before 2021. |

Raw API responses are cached in `data/raw/` as parquet, each with a JSON sidecar recording the indicator, countries, year range and fetch time — so a rebuild is reproducible and runs offline.

**Two rules the code enforces:**

- **One source per indicator.** Every numeric series is WDI, applied identically to all countries. The IMF figures in [`docs/myanmar-precoup-calibration-reference.md`](docs/myanmar-precoup-calibration-reference.md) are a cross-check only — they sit on a different fiscal-year basis, and mixing them in would corrupt the counterfactual.
- **Gaps stay visible.** Nothing is silently filled. Interpolation is a separate, labelled artifact, and series that go dark are reported rather than quietly extended.

Modeling decisions (donor pool, treatment year, the 2011 window) live in [`src/amber/config.py`](src/amber/config.py), not scattered through the logic.

---

## Status

🟡 **Early.** Data layer complete; modeling not started.

`amber.modeling` (synthetic control, system dynamics, index) and `amber.api` are stubs.

### Roadmap
- [x] Scope + methodology
- [x] Collect pre-coup plans & baseline trajectory
- [x] **Data layer** — fetch, cache, and clean the indicator panel
- [ ] Past reconstruction + combined index (in progress)
- [ ] Synthetic-control counterfactual
- [ ] System-dynamics future model
- [ ] Frontend: interactive scenarios + deploy

---

*A portfolio project. The name is a placeholder for a question: what colour is a future that didn't happen?*

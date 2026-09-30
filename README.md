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

![Real GDP per capita, 2011–2024: Myanmar against six regional peers](reports/figures/gdp_pc_divergence.png)

*Real GDP per capita (constant 2015 US$, log scale). Myanmar tracked its peers through 2019, then broke away from them. The counterfactual layer will estimate how much of that gap the 2021 coup accounts for, separately from COVID.*

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
make index        # development index + charts (see below)
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

## Development index

The combined development index is built from three pillars. Each one is the geometric mean of its indicators:

| Pillar | Indicators |
|---|---|
| **Economy** | GDP per capita · GDP growth · FDI net inflows · poverty headcount ($2.15/day) |
| **Innovation / technology** | Internet users · mobile subscriptions · high-tech exports |
| **Human development** | Life expectancy · under-5 mortality · secondary enrollment · health expenditure |

It is built in three steps, and every parameter lives in [`config.py`](src/amber/config.py):

1. **Normalize.** Each indicator is rescaled to [0, 1] against **fixed goalposts**: a low and a high bound per indicator, set in config and never recomputed. Every country-year sits on the same ruler, whether it's historical, a counterfactual or a 2035 projection. Adding a country or a new data vintage can't change a past score. Pre-2011 rows are excluded because military-era statistics aren't reliable enough to calibrate against.
   - **Polarity.** Poverty and under-5 mortality are lower-is-better, so they're inverted: `(high − x) / (high − low)`.
   - **Log income.** GDP per capita is taken as `ln(x)` first, following the HDI. An extra $1,000 matters more at $1,000 per head than at $5,000.
   - **Floor.** Scores are clipped to [0.01, 1], so no single worst value can drive a geometric mean to zero.
2. **Pillar sub-index.** The geometric mean of the normalized indicators *observed* in that country-year. Missing isn't scored as zero. A `coverage` column records what share of the pillar's indicators were present.
3. **Combined index.** `exp(Σ wᵢ · ln pᵢ / Σ wᵢ)` across the three pillars. The weights default to equal and are renormalized, so they can be given on any scale. A country-year gets a combined score only if every pillar with a positive weight is present. Otherwise a strong pillar would stand in for a missing one.

Geometric means are used throughout so that a strong economy can't hide a collapsing health system.

**Goalposts.** A published standard is used wherever one exists. The other bounds were seeded once from the 2011–2024 range: padded by 25% of the observed span on each side, clamped to the indicator's natural limits (a percentage can't pass 100), rounded outward, then frozen. The source of every bound is recorded in [`config.GOALPOSTS`](src/amber/config.py).

| Indicator | Low | High | Source |
|---|---|---|---|
| Life expectancy (years) | 20 | 85 | UNDP HDR 2025 Technical Notes (HDI) |
| Under-5 mortality (per 1,000) | 2.6 | 130 | Sustainable Development Report 2026 (SDG Index) |
| GDP per capita (2015 US$, log) | 475 | 6,850 | Seeded |
| GDP growth (%) | −17.5 | 14.5 | Seeded |
| FDI net inflows (% GDP) | −3 | 14.5 | Seeded |
| Poverty headcount (%) | 0 | 39 | Seeded, clamped at 0 |
| Internet users (%) | 0 | 100 | Seeded, clamped to 0–100 |
| Mobile subscriptions (per 100) | 0 | 205 | Seeded, clamped at 0 |
| High-tech exports (% mfg.) | 0 | 55.5 | Seeded, clamped at 0 |
| Secondary enrollment (% gross) | 32.5 | 112.5 | Seeded |
| Health expenditure (% GDP) | 0 | 8 | Seeded, clamped at 0 |

The HDI's income goalposts ($100–$75,000) aren't used. They apply to GNI per capita at 2017 PPP, which is a different basis from this series. The panel's own min-max (`--normalization pooled`) is still available for comparison, but it doesn't have the stability described above.

```bash
make index                                                         # table + charts
python scripts/build_index.py --weights economy=2,innovation=1,human_development=1
```

This writes `data/processed/index.csv`, with columns `country_iso3, country_name, year, series, value, coverage`, and renders the charts below to [`reports/figures/`](reports/figures/). [`notebooks/01_reconstruction.ipynb`](notebooks/01_reconstruction.ipynb) walks through the same build step by step. Its outputs are stripped in git, so run it to see the charts inline.

![Combined development index, 2011–2024, all seven countries](reports/figures/combined_index_all_countries.png)

**Coverage moves pillars.** When an indicator stops reporting, the pillar is computed from the ones that remain, and part of any change reflects that. Every partial-coverage point is drawn as a hollow ring. The clearest case: Bangladesh's high-tech exports score near the floor and stop reporting after 2018, so its innovation pillar rises from 0.11 to 0.39 in 2019 without any real change. For Myanmar, poverty data exists only for 2015–2017, secondary enrollment stops after 2018, and internet use stops after 2020.

![Myanmar's three pillar sub-indices, 2011–2024](reports/figures/myanmar_pillars.png)

---

## Status

🟡 **Early.** Data layer and past reconstruction complete; counterfactual next.

`amber.modeling.synthetic_control`, `amber.modeling.system_dynamics` and `amber.api` are stubs.

### Roadmap
- [x] Scope + methodology
- [x] Collect pre-coup plans & baseline trajectory
- [x] **Data layer** — fetch, cache, and clean the indicator panel
- [x] **Past reconstruction + combined index**
- [ ] Synthetic-control counterfactual (next)
- [ ] System-dynamics future model
- [ ] Frontend: interactive scenarios + deploy

---

*A portfolio project. The name is a placeholder for a question: what colour is a future that didn't happen?*

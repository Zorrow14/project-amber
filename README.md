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

*Real GDP per capita (constant 2015 US$, log scale). Myanmar tracked its peers through 2019, then broke away from them. The [counterfactual](#counterfactual) estimates that by 2024, Myanmar's GDP per capita was about a quarter below a synthetic no-coup Myanmar.*

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
make sc           # synthetic-control counterfactual + charts
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

## Counterfactual

**The method in plain terms.** No single country shows what Myanmar would have looked like without the coup. The [synthetic control method](https://en.wikipedia.org/wiki/Synthetic_control_method) builds a comparison instead: a weighted blend of the six peers that didn't rupture in 2021, with the weights chosen so the blend tracks real Myanmar as closely as possible from 2011 to 2020. The weights can't be negative and must add up to 100%, so "synthetic Myanmar" always sits within the range of real countries and never extrapolates past them. After 2021, the gap between real and synthetic Myanmar is the estimate.

| Outcome | Synthetic Myanmar | Pre-2021 fit (RMSE) | Credible | 2024 gap | Placebo rank |
|---|---|---|---|---|---|
| **Real GDP per capita** | 61% Nepal + 39% Cambodia | $33 (2.8% of level) | Yes | **−$413 (−26%)** | 1st of 7, p = 0.14 |
| **Combined development index** | 57% Nepal + 43% Cambodia | 0.070 (23% of level) | **No** | −0.118 | 6th of 7, p = 0.86 |

<img src="reports/figures/sc_gdp_pc_weights.png" width="49%" alt="Donor weights for GDP per capita"> <img src="reports/figures/sc_combined_index_weights.png" width="49%" alt="Donor weights for the combined index">

### GDP per capita

Synthetic Myanmar tracks the real one closely through 2019, and the two separate from 2020. By 2024, real GDP per capita is **$1,158 against a synthetic $1,571**.

![Real GDP per capita: Myanmar and synthetic Myanmar, 2011–2024](reports/figures/sc_gdp_pc_actual_vs_synthetic.png)

**How to read the inference.** Each donor is refitted as if *it* had been treated in 2021, matched only against the other donors. If Myanmar's gap is real, its post-2021 miss relative to its pre-2021 fit (the post/pre RMSE ratio) should stand out. Myanmar's ratio is 9.9, the highest of the seven. The pseudo p-value is the share of units whose ratio is at least Myanmar's, here 1/7 = 0.14. **That is the smallest p-value seven units can produce.** Ranking first is the strongest result available, but it can never show p < 0.05. The two faint lines are donors on the edge of the donor pool (Indonesia and Nepal) that the others can't match. Their "gaps" reflect a failed fit, not an effect.

![Myanmar's GDP-per-capita gap against the placebo gaps](reports/figures/sc_gdp_pc_placebo_gaps.png)

**How robust it is:**

- **Direction: robust.** Dropping either weighted donor keeps a large negative gap in 2024: −$359 without Cambodia, and −$783 without Nepal. The second refit is 100% Bangladesh with a much looser pre-fit ($127), and it forms the wide upper edge of the shaded band.
- **Size: specification-dependent.** Across fit choices the 2024 gap ranges from −24% (series rebased to 2011 = 100) through −26% (default) to −34% (fit ending 2019). Ending the fit in 2019 moves Myanmar to 2nd of 7 (p = 0.29).
- **In-time placebo.** With a fake treatment in 2017, the gap stays near zero for 2017–2019 (+$19, +$6, −$5). The −$165 in 2020 is the anomaly described below.

**The 2020 problem.** WDI records Myanmar on its October–September fiscal year, and assigns each fiscal year to the calendar year containing most of its months. So "2020" is October 2019 to September 2020, entirely before the coup, and it stays in the fit because COVID hit the donors too. But Myanmar's 2020 growth reads −9.1%, below every donor. (The World Bank's own estimate at the time was +0.5%, so the series has since been revised.) No blend of donors can reach that value. "2021" runs October 2020 to September 2021, so the first post-treatment point includes four pre-coup months.

**What the gap measures.** The gap is the combined effect of everything that hit Myanmar and not its peers from 2021 onward. That is mainly the coup and its aftermath, but it also includes anything else specific to Myanmar in those years. It is an estimate against a constructed comparison, not a forecast.

### Combined development index

The same method fails here, and the chart says so. Myanmar starts **below every donor** in 2011–2013, and a blend of donors can't go lower than its lowest member. The pre-fit misses by about a quarter of Myanmar's own level. Rebasing doesn't help either: Myanmar's index grew faster than any donor's in relative terms. So this result is **inconclusive**. It does not show that there was no effect.

![Combined development index: Myanmar and synthetic Myanmar](reports/figures/sc_combined_index_actual_vs_synthetic.png)

![Myanmar's combined-index gap against the placebo gaps](reports/figures/sc_combined_index_placebo_gaps.png)

```bash
make sc                                                              # tables + charts
python scripts/build_synthetic_control.py --pre-period-end 2019      # drop 2020 from the fit
python scripts/build_synthetic_control.py --rebase                   # 2011 = 100 variant
```

This writes to `data/processed/`:

- `synthetic_control`: actual, synthetic and gap by year
- `sc_weights`
- `sc_placebo`: Myanmar plus every placebo gap
- `sc_placebo_time`
- `sc_leave_one_out`
- `sc_metrics`: fit, p-value, the in-time ratio, the leave-one-out spread, and both donor counts: `n_weighted_donors` (weight ≥ 1%, the count most papers report) and `n_effective_donors` (1/Σw², which shows how concentrated the weights are). It also carries `credible`, the same verdict the captions state: true only when pre-RMSE is at most `SC_CREDIBLE_PRE_RMSE_SHARE` (10%) of Myanmar's pre-period level.

Every setting is in [`config.py`](src/amber/config.py) under *Synthetic control*. [`notebooks/02_counterfactual.ipynb`](notebooks/02_counterfactual.ipynb) walks through it step by step.

---

## Status

🟡 **Early.** Data layer, past reconstruction and counterfactual complete; future model next.

`amber.modeling.system_dynamics` and `amber.api` are stubs.

### Roadmap
- [x] Scope + methodology
- [x] Collect pre-coup plans & baseline trajectory
- [x] **Data layer** — fetch, cache, and clean the indicator panel
- [x] **Past reconstruction + combined index**
- [x] **Synthetic-control counterfactual**
- [ ] System-dynamics future model (next)
- [ ] Frontend: interactive scenarios + deploy

---

*A portfolio project. The name is a placeholder for a question: what colour is a future that didn't happen?*

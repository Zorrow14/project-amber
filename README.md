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
- **Modeling:** pandas · numpy · scipy (SLSQP synthetic-control weights, least-squares calibration) · a hand-written system-dynamics simulator
- **API:** FastAPI · Pydantic v2, serving a committed data snapshot
- **Frontend:** React · TypeScript · Vite · Recharts
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
make sd           # future scenarios + charts (make models = sc + sd)
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
| **Economy** | GDP per capita · GDP growth · FDI net inflows |
| **Innovation / technology** | Internet users · mobile subscriptions |
| **Human development** | Life expectancy · under-5 mortality · secondary enrollment · health expenditure |

**Two panel series are kept as history but left out of the index.** Amber compares the same index across the past, the counterfactual and 2035 projections, so it can only contain indicators all three can produce:

- **Poverty headcount ($2.15/day).** Myanmar has three observations (2015–2017). In the index it entered Myanmar's score for those three years only, which is a change of composition rather than of development.
- **High-tech exports.** Myanmar's series is erratic (0.2–7.5% of manufactured exports) and has no structural driver, so no counterfactual or projection can produce it.

Both remain in the panel, and their polarity and goalposts stay configured, so reversing the exclusion is a one-line change to `config.INDEX_EXCLUDED`. The cost is breadth: the innovation pillar now measures connectivity adoption only.

It is built in three steps, and every parameter lives in [`config.py`](src/amber/config.py):

1. **Normalize.** Each indicator is rescaled to [0, 1] against **fixed goalposts**: a low and a high bound per indicator, set in config and never recomputed. Every country-year sits on the same ruler, whether it's historical, a counterfactual or a 2035 projection. Adding a country or a new data vintage can't change a past score. Pre-2011 rows are excluded because military-era statistics aren't reliable enough to calibrate against.
   - **Polarity.** Under-5 mortality is lower-is-better, so it's inverted: `(high − x) / (high − low)`.
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
| Internet users (%) | 0 | 100 | Seeded, clamped to 0–100 |
| Mobile subscriptions (per 100) | 0 | 205 | Seeded, clamped at 0 |
| Secondary enrollment (% gross) | 32.5 | 112.5 | Seeded |
| Health expenditure (% GDP) | 0 | 8 | Seeded, clamped at 0 |

The HDI's income goalposts ($100–$75,000) aren't used. They apply to GNI per capita at 2017 PPP, which is a different basis from this series. The panel's own min-max (`--normalization pooled`) is still available for comparison, but it doesn't have the stability described above.

```bash
make index                                                         # table + charts
python scripts/build_index.py --weights economy=2,innovation=1,human_development=1
```

This writes `data/processed/index.csv`, with columns `country_iso3, country_name, year, series, value, coverage`, and renders the charts below to [`reports/figures/`](reports/figures/). [`notebooks/01_reconstruction.ipynb`](notebooks/01_reconstruction.ipynb) walks through the same build step by step. Its outputs are stripped in git, so run it to see the charts inline.

![Combined development index, 2011–2024, all seven countries](reports/figures/combined_index_all_countries.png)

**Coverage moves pillars.** When an indicator stops reporting, the pillar is computed from the ones that remain, and part of any change reflects that. Every partial-coverage point is drawn as a hollow ring. Myanmar reports all nine indicators for 2011–2018. Then secondary enrollment stops after 2018, internet use after 2020, and health expenditure is missing for 2024, so its 2024 score rests on six of nine. The future-scenarios chart measures what that does: in 2024 the model's index is 0.027 higher over all nine indicators than over the six Myanmar reports.

On this composition Myanmar's index rises from 0.12 in 2011 to 0.53 in 2019 and is 0.52 in 2024, level with Bangladesh (0.52) and Nepal (0.50). Read the post-2020 points with their rings in mind.

![Myanmar's three pillar sub-indices, 2011–2024](reports/figures/myanmar_pillars.png)

---

## Counterfactual

**The method in plain terms.** No single country shows what Myanmar would have looked like without the coup. The [synthetic control method](https://en.wikipedia.org/wiki/Synthetic_control_method) builds a comparison instead: a weighted blend of the six peers that didn't rupture in 2021, with the weights chosen so the blend tracks real Myanmar as closely as possible from 2011 to 2020. The weights can't be negative and must add up to 100%, so "synthetic Myanmar" always sits within the range of real countries and never extrapolates past them. After 2021, the gap between real and synthetic Myanmar is the estimate.

| Outcome | Synthetic Myanmar | Pre-2021 fit (RMSE) | Credible | 2024 gap | Placebo rank |
|---|---|---|---|---|---|
| **Real GDP per capita** | 61% Nepal + 39% Cambodia | $33 (2.8% of level) | Yes | **−$413 (−26%)** | 1st of 7, p = 0.14 |
| **Combined development index** | 72% Bangladesh + 28% Cambodia | 0.085 (24% of level) | **No** | −0.026 | 7th of 7, p = 1.00 |

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

## Future scenarios

**These are scenarios, not forecasts.** The future layer is a small model that shows how Amber's assumptions play out to 2035 under different paths for stability and policy. It does not predict what will happen.

**The model in plain terms.** It tracks four quantities, called stocks, for Myanmar:

- **Physical capital**
- **Human capital**, measured through life expectancy
- **Connectivity**, measured as internet users
- **Institutional stability**, which each scenario sets

Output depends on all four. The **feedback loop** runs like this: connectivity raises productivity, productivity raises output, and output pays for both investment and the further spread of connectivity. Stability multiplies productivity, so a more stable country gets more out of the whole loop. Policy **levers** act as multipliers on the calibrated behaviour, where 1.0 means reform-era behaviour: `fdi_openness`, `education_spend`, `health_spend` and `connectivity_investment`. These are the sliders in the app's Future view.

The model is a hand-written annual difference-equation simulator in numpy. The project plan named PySD, and this is a deliberate change: every equation stays visible in the code and can be tested offline, with no separate model file to keep in sync. The equations are in [`system_dynamics.py`](src/amber/modeling/system_dynamics.py).

**Scenarios** (data in [`config.SCENARIOS`](src/amber/config.py)):

| Scenario | Stability | Levers (from 2025) |
|---|---|---|
| Actual continuation | Post-coup level, held | Unchanged |
| No coup | Reform-era level throughout | Unchanged |
| Partial recovery | Post-coup to 2024, then halfway back by 2035 | Unchanged |
| Reform push | Reform-era level throughout | Education and connectivity ×1.5 (MSDP Strategy 3.7) |

![Myanmar's development index under four scenarios to 2035](reports/figures/sd_combined_index_fan.png)

**Headline, 2035** (ensemble median, with the p10–p90 range in brackets):

| Scenario | GDP per capita | Combined index |
|---|---|---|
| Actual continuation | $1,726 ($1,407–$2,177) | 0.626 (0.578–0.659) |
| No coup | **$2,273** ($1,956–$2,734) | **0.678** (0.642–0.705) |
| Partial recovery | $1,960 ($1,659–$2,390) | 0.657 (0.616–0.685) |
| Reform push | $2,314 ($1,990–$2,782) | 0.696 (0.670–0.722) |

**The gap between scenarios, paired member by member.** Every scenario runs on the same 200 parameter draws, so the right comparison is each member against itself. It isn't whether two bands overlap. By 2035, no coup ends **+$534 above actual continuation** in GDP per capita (p10–p90 +$324 to +$730, or +17% to +48%), and **+0.055 on the index** (+0.033 to +0.079). It ends above actual continuation in **all 200 members**. The marginal GDP bands do overlap, because the members disagree more about the overall growth path than about the gap between scenarios. These gaps are in `sd_gaps`.

**The index means the same thing everywhere.** The model produces exactly the nine index indicators, so a projected score and a historical one measure the same thing. What the model can't reproduce is Myanmar's reporting gaps. History after 2018 scores only the indicators Myanmar reports, while scenarios score all nine. The fan chart states the size of that step (+0.027 in 2024) and the model's own miss (+0.039), so a coverage change is never read as a scenario effect. The `combined` row of `sd_metrics` carries `composition_gap`, and its error is computed like for like: the model scored over the same indicators as history each year.

![Real GDP per capita under no coup and actual continuation](reports/figures/sd_gdp_pc_scenarios.png)

**How it is calibrated, and how far to trust it:**

- **Fit.** Thirteen parameters are fitted by bounded least squares to Myanmar's 2011–2024 indicators, measured on the index's goalpost scale. The backtest error is **0.068 in index units**, within the 0.10 credibility gate, so `credible = true` in `sd_metrics`. Above that gate, every caption would call the scenarios illustrative dynamics. The backtest is in-sample, because the coup's effect can't be estimated without data from after 2021.
- **Two parameters are assumptions, not estimates, and the bands carry them.** The data can't tell apart values of the connectivity effect on productivity (κ, the leapfrog channel Amber is built around) from 0 to 0.5, or of the savings rate from 0.2 to 0.5. The central run holds them at 0.25 and 0.30. But the ensemble spreads across every low, assumed and high combination (nine nodes), refitting all 13 calibrated parameters to history at each. Every run re-checks that they really are unidentified: all eight off-centre nodes fit within ±0.0035 of the central backtest error, against a 0.01 tolerance (`sd_profile`, column `flat`). At the least plausible corner (κ = 0.5, savings 0.5), the refit pushes TFP growth to its floor of 0, and `sd_profile` flags it in `at_bound`. γ, the strength of the stability channel, stays estimated (0.76).
  - **Why κ = 0.25:** it is a one-off level effect of 2.5% of productivity per 10 points of internet use. That is deliberately conservative next to [Czernich et al. (2011)](https://ideas.repec.org/a/ecj/econjl/v121y2011i552p505-532.html), who find that 10 points of broadband raised annual growth by 0.9–1.5 points across the OECD.
- **Consistency with phase 3.** Over 2021–2024 the no-coup scenario sits **5.2%** from the credible synthetic control, within the 10% tolerance. The COVID shock is modelled as a lasting loss, because none of the six donors returned to its pre-2020 trend. That assumption came from the same donors the synthetic control uses, so the two checks aren't fully independent.
- **Known misses.** The model expects recovery growth after the coup, but Myanmar stagnated. By 2024 the model is 7.3% above actual, so **actual continuation is likely optimistic**. Myanmar's internet data stop in 2020, so nothing constrains connectivity after that. The model saturates it by the mid-2020s in every scenario, which is why reform push adds only about $40 over no coup, most of it from education. Health spending as a share of GDP is the worst-fitting indicator (0.125).

![Backtest: the calibrated model against Myanmar, 2011–2024](reports/figures/sd_backtest.png)

![The model's stocks under each scenario](reports/figures/sd_stocks.png)

```bash
make sd                                                  # calibrate, run scenarios, write + chart
make models                                              # make sc, then make sd
python scripts/build_system_dynamics.py --ensemble-size 500
```

This writes to `data/processed/`:

- `sd_trajectory`: every stock, modeled indicator, pillar and the combined index, by scenario and year, at p10, p50 and p90
- `sd_scenarios`
- `sd_calibration`, which flags any fitted parameter that ends up at the edge of its allowed range (`at_bound`) and marks the `unidentified` ones
- `sd_metrics`: backtest error overall and per indicator, the `credible` gate, the phase 3 overlap check, and the combined index's `composition_gap`
- `sd_profile`: one row per node of the unidentified parameters, with the backtest error, the `flat` check, `at_bound`, and every refitted parameter, so the ensemble can be rebuilt without refitting
- `sd_gaps`: each scenario's paired gap from actual continuation, at p10, p50 and p90, with `share_above`

[`notebooks/03_future.ipynb`](notebooks/03_future.ipynb) walks through it step by step and ends with a "build your own scenario" cell.

---

## App

The web app puts all three layers behind one interface. Its FastAPI backend serves the model outputs, and it has four views:

- **Overview** – what Amber is, and the GDP-per-capita divergence.
- **Past** – GDP per capita and the combined index for all seven countries. Three pillar-weight sliders recompute the index live.
- **Counterfactual** – for each outcome: real against synthetic Myanmar, the gap against the placebos, and the donor weights.
- **Future** – choose a stability path and move the policy levers. Each change reruns the calibrated model live and redraws the fan chart.

![The Future view: the no-coup scenario's p10–p90 band against history, with its caveats](docs/images/app-future.png)

**What is precomputed and what runs live.** Only two things are computed when you move a control, and both are cheap forward passes. Nothing is ever refitted on a request.

| Endpoint | Computed | What it serves |
|---|---|---|
| `GET /meta` | once, at startup | Countries, indicators, pillars and default weights, levers (range, step, default), scenarios and framing text. All of it comes from `config.py`, so the UI hardcodes none of it. |
| `GET /panel` | precomputed | Tidy indicator series with `imputed` and dark-series flags |
| `GET /index?weights=economy=2,innovation=1,human_development=1` | **live**: `compute_index` | Pillar and combined index for every country, with `coverage` on every row |
| `GET /counterfactual` | precomputed | For each outcome: actual, synthetic and gap, donor weights, placebos (with `poor_fit`), in-time placebo, the leave-one-out band, and the metrics, including `credible`, `pre_rmse_share`, `pseudo_p_value`, `n_effective_donors` and `n_weighted_donors` |
| `GET /scenarios` | precomputed | Every scenario at p10, p50 and p90 (stocks, indicators, pillars, combined), paired gaps, and the `sd_metrics` verdicts |
| `POST /simulate` | **live**: `run_scenarios` | Same shape as a scenario. Levers override a named scenario. It runs on the stored calibration and profile nodes, and a named scenario reproduces its precomputed run to about 10⁻¹⁰. |

Bad input gets a 422 with a readable message: an unknown pillar, lever, scenario, indicator or country; a lever out of range; negative, all-zero or malformed weights.

**The caveats travel with the data.** Every response that carries a modeled series also carries its verdict, and the UI shows it wherever the series appears:
- An index row with `coverage` below 1 is drawn as a hollow point.
- A counterfactual with `credible: false` gets a banner saying it is not a credible effect estimate. Its charts are badged "illustrative", and its gap is not reported as an effect.
- The Future view always shows "Scenarios, not forecasts". It switches to "illustrative dynamics" if the model fails its backtest gate, and states the phase 3 overlap check and the composition step.

A frontend test checks that the banner renders for a `credible: false` payload, and CI runs it.

```bash
make api            # uvicorn on :8000, serving data/release
make frontend-install
make frontend-dev   # Vite on :5173, calling the API
```

`AMBER_DATA_SOURCE=processed make api` serves your latest `make models` output instead of the committed snapshot. The frontend reads `VITE_API_BASE_URL`, which defaults to `http://localhost:8000`.

---

## Deployment

The deployed API never calls the World Bank. It serves **`data/release/`**, a committed snapshot of the 15 tables it needs (about 0.6 MB).
- Its `manifest.json` records the build time, the source commit, and a SHA-256 hash and row count for every file.
- The API checks those hashes at startup, so a hand-edited or half-regenerated snapshot fails loudly.

Regenerate it deliberately after the models change, never by hand:

```bash
make panel && make index && make models   # rebuild the tables
make release                              # copy them into data/release + manifest
git add data/release && git commit -m "Refresh the release snapshot"
```

Nothing below has been run for this repository. The steps are for you to follow, and no secrets are involved.

1. **API on Render.** Create a Blueprint from this repository; [`render.yaml`](render.yaml) defines the `amber-api` web service.
   - It installs with `pip install -e .` and runs `uvicorn amber.api.main:app` with `AMBER_DATA_SOURCE=release`.
   - Its health check is `/health`.
   - Once it's live, note its URL (e.g. `https://amber-api.onrender.com`).
2. **Frontend on Vercel.** Import the repository with **Root Directory = `frontend`**. [`frontend/vercel.json`](frontend/vercel.json) sets the Vite build. Then:
   - Add the environment variable `VITE_API_BASE_URL` = the Render URL.
   - Deploy. Routes are hash-based, so no rewrites are needed.
3. **Connect them.** In Render, set `AMBER_CORS_ORIGINS` to the Vercel URL (comma-separate several, e.g. a preview domain), and redeploy the API.
4. **Check.**
   - `GET <render-url>/health` should report `"source": "release"` with the manifest's `built_at` and commit.
   - The app's footer shows the same snapshot.

Both `.env.example` files ([root](.env.example), [frontend](frontend/.env.example)) list every variable. On Render's free tier the service sleeps when idle, so the first request after a pause takes a few seconds.

---

## Status

🟢 **Complete.** All three layers, the API that serves them and the web app are built, tested and ready to deploy. Every number is an estimate or a scenario, and the app says so wherever it shows one.

### Roadmap
- [x] Scope + methodology
- [x] Collect pre-coup plans & baseline trajectory
- [x] **Data layer** — fetch, cache, and clean the indicator panel
- [x] **Past reconstruction + combined index**
- [x] **Synthetic-control counterfactual**
- [x] **System-dynamics future scenarios**
- [x] **API + frontend** — FastAPI over a committed snapshot, React app with live weights and levers
- [x] **Deploy config** — Render (API) and Vercel (frontend), hermetic release data

---

*A portfolio project. The name is a placeholder for a question: what colour is a future that didn't happen?*

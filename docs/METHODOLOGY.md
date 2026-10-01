# Methodology

This document explains, in plain prose, how Amber works and why each design choice was made. It is the long form of the decisions the code enforces.

Every number and threshold named here lives in [`src/amber/config.py`](../src/amber/config.py), the single source of truth. Constants are written `LIKE_THIS` so you can find them there. If this document and `config.py` ever disagree, `config.py` is right and this document is out of date.

The honest limits of each method are in [LIMITATIONS.md](LIMITATIONS.md).

**Contents**

1. [Scope and data](#1-scope-and-data)
2. [The development index](#2-the-development-index)
3. [The counterfactual: synthetic control](#3-the-counterfactual-synthetic-control)
4. [The future: a system-dynamics model](#4-the-future-a-system-dynamics-model)
5. [From models to the app](#5-from-models-to-the-app)

---

## 1. Scope and data

**The question.** Amber asks three questions about one country:
- What happened to Myanmar's development after the 2011 reforms?
- What might have happened without the February 2021 coup?
- What could still happen, to 2035?

Each question has its own method. All three share one country-year panel and one development index, so their answers are measured on the same ruler.

**The panel.** Eleven World Bank WDI indicators (`INDICATORS`), for Myanmar and six regional peers (`DONOR_POOL`: Vietnam, Cambodia, Bangladesh, Lao PDR, Nepal and Indonesia), from 2000 to 2024 (`YEAR_START`, `YEAR_END`).

- **One source, one convention.** Every series comes from WDI and is treated identically for every country. Mixing sources would be convenient, for example IMF calendar-year growth for Myanmar beside WDI fiscal-year growth for the peers, but it would make the comparison meaningless. So it is treated as a defect.
- **The modeling window starts in 2011** (`MODELING_WINDOW_START`). Statistics from the military era before 2011 are not reliable enough to calibrate against. They are fetched, then flagged (`pre_2011`) and excluded.
- **Gaps stay visible.** Missing values are interpolated linearly, and only between two real observations. Nothing is extrapolated past the last real value, every interpolated cell carries an `imputed` flag, and series that stop reporting before 2021 are marked `is_dark` in the coverage report.
- **Raw pulls are cached unmodified**, with a provenance sidecar, so the path from raw data to the panel is scripted and reproducible offline.

**The treatment point** is February 2021 (`TREATMENT_YEAR`). WDI records Myanmar on its October–September fiscal year and labels each year by the calendar year that holds most of its months. So "2021" runs from October 2020 to September 2021 and includes four pre-coup months (`FISCAL_YEAR_MESSAGE`). Every chart of a WDI series carries that note.

---

## 2. The development index

The index answers the question "how developed?" with one number per country-year. Its job is to stay comparable across history, the counterfactual and the projections. Each step below exists to protect that.

### Pillars and indicators

There are three pillars (`Pillar`). The indicator-to-pillar mapping is in `INDICATORS`.

| Pillar | Indicators in the index |
|---|---|
| Economy | GDP per capita, GDP growth, FDI net inflows (% GDP) |
| Innovation / technology | Internet users (%), mobile subscriptions (per 100) |
| Human development | Life expectancy, under-5 mortality, secondary enrollment, health expenditure (% GDP) |

**Two panel series are kept as history but excluded from the index** (`INDEX_EXCLUDED`, with the reasons recorded in config). The index holds only what all three layers can produce (`INDEX_INDICATORS`):

- **Poverty headcount.** Myanmar has three observations, so including it would make a composition change look like development.
- **High-tech exports.** The series is erratic and no structural model drives it.

Excluding them is a deliberate trade. The innovation pillar loses breadth and now measures connectivity adoption only. In return, a 2035 projection and a 2015 observation measure the same thing.

### Step 1: Normalize against fixed goalposts

Each indicator is rescaled to [0, 1] against a fixed low and high bound (`GOALPOSTS`): `(x − low) / (high − low)`.

- **Published standards are used verbatim wherever they exist.** Life expectancy uses 20–85 from the UNDP HDI. Under-5 mortality uses 2.6–130 from the SDG Index.
- **The other bounds were seeded once and frozen.** Each took the 2011–2024 range, padded it by `GOALPOST_PADDING` (25% of the span), clamped it to the natural domain (a percentage cannot pass 100) and rounded outward. The source of every bound is recorded.

Fixed goalposts, rather than recomputing min-max on each run, are the foundation of the whole project. With min-max, adding a country, a new data vintage or a projected year would move every past score. With fixed goalposts, a counterfactual or a 2035 value lands on the same ruler as history. Goalposts are never recomputed from data at runtime.

Three adjustments come before aggregation:

- **Polarity** (`INDICATOR_POLARITY`). Lower-is-better indicators (under-5 mortality) are inverted. Every indicator must declare a polarity, and the import-time check refuses one that doesn't.
- **Log income** (`LOG_TRANSFORM`). GDP per capita is taken as `ln(x)` before scaling, as in the HDI. An extra $1,000 matters more at $1,000 per head than at $5,000.
- **Floor** (`NORMALIZED_FLOOR` = 0.01). Scores are clipped to [0.01, 1], so one worst-case value cannot drive a geometric mean to zero. A value outside its goalposts is clipped and logged as a warning. If that warning fires on real data, a goalpost needs widening.

### Step 2: Pillar sub-index

A pillar is the **geometric mean** of its normalized indicators that were *observed* that year. A missing indicator is not scored as zero, which would punish non-reporting as if it were collapse.

Each row records **`coverage`**, the share of the pillar's indicators that were present. When an indicator stops reporting, part of any change in the pillar is a change of composition, not of development. Myanmar loses secondary enrollment after 2018, internet use after 2020 and health expenditure in 2024. Every partial-coverage point is drawn as a hollow ring, in the committed charts and in the app (`COVERAGE_MESSAGE`).

### Step 3: Combined index

The combined index is a **weighted geometric mean** of the three pillars: `exp(Σ wᵢ ln pᵢ / Σ wᵢ)`.

- The weights default to equal (`DEFAULT_PILLAR_WEIGHTS`), are renormalized, and are a user control in the app. "How you define development" is a setting, not a hidden assumption.
- **Geometric, not arithmetic.** A strong economy cannot hide a collapsing health system: weakness in any pillar pulls the whole score down.
- **A combined score requires every positively-weighted pillar.** If one is missing, the row is not scored, because a strong pillar would otherwise stand in for the absent one.
- **Combined coverage counts only indicators in positively-weighted pillars**, so zero-weighting a pillar doesn't drag coverage down.

---

## 3. The counterfactual: synthetic control

### The idea

No single country shows what Myanmar would have looked like without the coup, so Amber builds one. **Synthetic Myanmar** is a weighted blend of the donor countries, with weights chosen so the blend tracks real Myanmar as closely as possible over the pre-treatment period (2011–`SC_PRE_PERIOD_END`, that is, 2011–2020). After 2021, the gap between real and synthetic Myanmar is the estimate.

### The donor pool

The donors are regional peers with no concurrent shock of their own (`DONOR_POOL`). A contaminated donor breaks the estimate, which is why **Sri Lanka is deliberately excluded**: its 2022 economic crisis would make a synthetic Myanmar built partly from Sri Lanka fall for reasons that have nothing to do with Myanmar. The pool is configurable, and its sensitivity is tested (leave-one-out, below).

### The weights

- **Convex.** Weights are non-negative and sum to one. This is what stops extrapolation: synthetic Myanmar always lies within the range of real countries. Unconstrained regression weights could "fit" Myanmar by combining donors with negative weights, which describes no real comparison.
- **Fitted on the outcome path.** The weights are fitted to the pre-period outcome series, z-scored, with an identity V matrix. `SC_PREDICTORS` is empty by design. Six donors cannot support nested V-optimization, and a pre-period outcome match is the transparent standard.
- **Solved reproducibly.** SLSQP runs with `SC_N_RESTARTS` seeded restarts (`SC_SEED`), so the result is deterministic.
- **Two donor counts are reported.** `n_weighted_donors` counts donors with weight ≥ `SC_WEIGHT_THRESHOLD` (1%), the conventional count. `n_effective_donors` is 1/Σw², which shows how concentrated the weights are.

All fit settings travel together in one frozen `SCSettings`, so placebos and refits cannot silently diverge from the base fit.

### Inference: placebos, not standard errors

With one treated unit and six donors there is no sampling distribution to draw a confidence interval from. Instead:

- **In-space placebos.** Each donor is refitted as if it had been treated in 2021, matched only against the *other* donors and never against Myanmar. If Myanmar's gap is real, its post/pre RMSE ratio should stand out. The **pseudo p-value** is the share of the seven units whose ratio is at least Myanmar's.
- **The floor is 1/7.** With seven units, the smallest possible p-value is 1/7 ≈ 0.14. The results therefore never say "significant at 5%". They say "ranks first of seven", which is the strongest statement available.
- **Poorly matched placebos.** A placebo whose own pre-fit error exceeds `SC_PLACEBO_POOR_FIT_MULTIPLE` (5×) Myanmar's is drawn faint and dashed: its "gap" reflects a failed fit, not an effect. It is still counted in the p-value.
- **In-time placebo.** A fake treatment in `SC_INTIME_PLACEBO_YEAR` (2017) should produce no gap.
- **Leave-one-out.** Each weighted donor is dropped in turn and the fit is redone. The spread of those refits is the shaded band. It shows whether the result rests on any single country.
- **Specification variants.** Quoted magnitudes come with two variants: the fit ending in 2019 (`--pre-period-end 2019`, because Myanmar's 2020 WDI value is an outlier no donor blend reaches) and series rebased to 2011 = 100 (`--rebase`).

### The credibility gate

**Pre-period fit comes first.** A synthetic control that cannot track Myanmar *before* the coup has no claim on what happened *after* it.

`SyntheticControlResult.credible` is true only when the pre-period RMSE is at most `SC_CREDIBLE_PRE_RMSE_SHARE` (10%) of Myanmar's pre-period level. That one property drives:
- the chart captions,
- the `credible` column in `sc_metrics`,
- the API's `credibility` block,
- the app's banner.

So the prose and the data cannot disagree.

A non-credible fit is **not a weaker estimate but no estimate.** Its gap is never presented as an effect.

| Outcome | Pre-fit error | Credible | Reading |
|---|---|---|---|
| Real GDP per capita | 2.8% of level | Yes | 2024 gap −26%; ranks 1st of 7 (p = 0.14) |
| Combined index | 23.6% of level | No | Inconclusive. Myanmar starts below every donor, and a convex blend cannot go lower than its lowest member. |

---

## 4. The future: a system-dynamics model

### Framing: scenarios, not forecasts

The future layer shows how Amber's assumptions play out to 2035 (`SD_HORIZON_END`) under different paths for stability and policy. It does **not** predict what will happen (`SCENARIO_FRAMING`). The framing appears wherever a projection does.

### The engine

The model is a hand-written annual difference-equation simulator in numpy ([`modeling/system_dynamics.py`](../src/amber/modeling/system_dynamics.py)). The project plan named PySD; this is a deliberate change. Every equation stays visible in the code and can be tested offline, with no separate model file to keep in sync.

### Stocks, the loop and the levers

It tracks four **stocks**:

- **Physical capital, K.** Accumulates investment and depreciates.
- **Human capital, H.** Life expectancy relative to 2011. It grows with education and health effort.
- **Connectivity, I.** Internet users. It spreads by diffusion, from existing users toward saturation, which is the S-curve Myanmar actually followed.
- **Institutional stability, S.** Set by the scenario, not modeled.

Output combines them in a Cobb-Douglas form:

> Y = A · (1+g)ᵗ · COVID loss · S^γ · (1 + κ·I/I_max) · K^α · H^β

**The feedback loop** Amber is built around: connectivity raises productivity (κ), productivity raises output, and output funds both investment and faster diffusion of connectivity. Stability multiplies productivity (γ), so a more stable country gets more out of the whole loop.

**Levers** (`LEVERS`) are multipliers on the calibrated reform-era behavior, where 1.0 means "as calibrated". They apply from `SD_PROJECTION_START` (2025), and their ranges are data in config:

| Lever | Acts on | Range |
|---|---|---|
| Investment openness (`fdi_openness`) | investment rate and FDI | 0.5–1.5 |
| Education spending (`education_spend`) | human-capital accumulation | 0.5–2.0 |
| Health spending (`health_spend`) | human-capital accumulation and health expenditure | 0.5–2.0 |
| Connectivity investment (`connectivity_investment`) | diffusion rate | 0.5–2.0 |

**Scenarios** (`SCENARIOS`) are data too. Stability is expressed as a *recovery path* r ∈ [0, 1], with S = S_post + r(1 − S_post), so a scenario stays meaningful whatever value calibration finds for post-coup stability. The four scenarios:
- actual continuation (r = 0);
- no coup (reform-era stability throughout);
- partial recovery (halfway back by 2035);
- reform push (no coup, plus education and connectivity ×1.5, following MSDP Strategy 3.7).

### From model to index

The model produces **exactly the nine index indicators** through `SD_INDICATOR_LINKS`, and `_check_system_dynamics_config()` refuses a mismatch. The modeled values are scored through the *same* `compute_index` on the same goalposts, one pseudo-country per ensemble member. There is no separate scoring path.

Shares (internet use, mobile subscriptions, enrollment) use saturating links (`LinkKind.BOUNDED`), because a power law would compound past its goalpost within the horizon.

**The composition step.** History loses indicators that Myanmar stopped reporting, while scenarios score all nine. In 2024 that difference alone lifts the modeled index by about 0.027 (`composition_gap` in `sd_metrics`). The backtest is scored like for like, on the same observed cells each year (`combined_matched`). The fan chart states the step, so a coverage change is never read as a scenario effect.

### Calibration and the backtest gate

- **The fit.** Thirteen parameters (`SD_PARAMETERS`, `calibrate=True`) are fitted by bounded least squares to Myanmar's 2011–2024 indicators, with residuals on the goalpost scale (index units), using `SD_CALIBRATION_RESTARTS` seeded starts.
- **The gate.** The backtest error is reported overall and per indicator. If the overall error (nRMSE) exceeds `SD_CREDIBLE_NRMSE` (0.10), the `credible` flag on the `overall` row of `sd_metrics` turns false. Every caption and the app then call the output "illustrative dynamics, not a calibrated projection" (`SD_NOT_CREDIBLE_MESSAGE`).
- **Current result.** The error is 0.068, so the gate passes. The backtest is in-sample: the coup's effect cannot be estimated without data from after 2021.
- **Bounds.** A fitted value that ends up on its bound is flagged `at_bound`, which signals weak identification or a strained corner.

### Unidentified parameters are profiled, not hidden

The data cannot distinguish between values of two parameters across their plausible ranges:
- κ (`connectivity_tfp`, the leapfrog channel) from 0 to 0.5;
- the savings rate from 0.2 to 0.5.

Both are marked `SDParameter.unidentified`. The central run holds them at assumed values (κ = 0.25, deliberately conservative against Czernich et al., 2011; savings 0.30).

Rather than let the uncertainty bands pretend these are known, `profile()` refits all thirteen calibrated parameters at every low/assumed/high combination: nine nodes, written to `sd_profile`. Every run re-checks that they really are unidentified, meaning each node fits within `SD_PROFILE_TOLERANCE` (0.01) of the central backtest error (the `flat` column). A steep node would mean the parameter *is* identified and should be calibrated instead. γ, the stability elasticity, is identified and stays calibrated.

### The ensemble and paired gaps

Each scenario runs as a `SD_ENSEMBLE_SIZE` (200) member ensemble. Members cycle through the profile nodes, and the calibrated parameters are jittered ±`SD_PARAM_JITTER` (15%) around each node's fit. The p10–p90 band is a **sensitivity range, not a confidence interval**: it ignores parameter correlation and model-structure error.

**Members share their draws across scenarios** (common random numbers). So the right way to compare two scenarios is member by member, the **paired gap** (`sd_gaps`, with `share_above`), not whether their marginal bands overlap. The bands can overlap because members disagree about the overall growth path even when every member agrees on the direction of the gap.

### Consistency with the counterfactual

The no-coup scenario and the synthetic control answer overlapping questions for 2021–2024. Their deviation is reported against `SD_SC_TOLERANCE` (10%) but never tuned away: currently 5.2% for GDP per capita. The two checks are not fully independent. COVID is modeled as a persistent level loss (`covid_persistence` = 1) because none of the donors returned to their pre-2020 trend, and that assumption came from the same donors.

---

## 5. From models to the app

**The precompute/live boundary.** Everything expensive runs offline (`make models`) and is copied into a committed, hash-checked snapshot (`data/release/`, `RELEASE_STEMS`, `manifest.json`).

The API loads it once at startup and never refits anything. Only two endpoints compute on request, and both are cheap forward passes:
- `/index` recomputes the index under the user's pillar weights.
- `/simulate` re-runs the ensemble from the stored calibration and profile nodes under the user's levers. A named scenario reproduces its precomputed run to about 10⁻¹⁰.

The API tests replace every fitting function with one that fails, so a regression here cannot pass unnoticed.

**Caveats travel with the data.** Every modeled payload carries its verdict (`coverage`, `credibility`, `sc_checks`), and the app renders it wherever the series appears:
- hollow points for partial coverage;
- a not-credible banner and an "Illustrative only" badge;
- "Scenarios, not forecasts" on every projection.

The frontend hardcodes nothing that config knows. Countries, indicators, weights, levers, scenarios, thresholds and caveat wording all come from `GET /meta`.

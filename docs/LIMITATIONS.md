# Limitations

Amber is built to be argued with. This document lists what it cannot tell you and where its numbers are weakest. It is part of the project, not a disclaimer appended to it: a result is only as useful as the reader's sense of how far to trust it.

The methods themselves are described in [METHODOLOGY.md](METHODOLOGY.md).

---

## Every forward number is a scenario, not a prediction

The future layer shows how stated assumptions play out under chosen paths for stability and policy. It does **not** say what will happen in Myanmar.

- **No probabilities.** No scenario is more likely for having been modeled, and the four scenarios are not a probability distribution.
- **The p10–p90 bands are a sensitivity range, not a confidence interval.** They reflect jittered parameters and the profiled unidentified ones. They do not include model-structure error, parameter correlation, or anything the model leaves out.
- **Known miss: the model is optimistic about the present.** After the coup it expects recovery growth, but Myanmar stagnated. By 2024 the model sits 7.3% above actual GDP per capita, so **"actual continuation" is likely optimistic**, and the gaps measured from it are likely understated.
- **The backtest is in-sample.** The model is calibrated and checked on the same 2011–2024 history, because the coup's effect cannot be estimated without post-2021 data. Passing the credibility gate means the model can reproduce the past; it does not show it can predict.

## The model rests on strong assumptions

- **Stability is an input, not an outcome.** Institutional stability is set by each scenario, not explained by the model. The model says nothing about *whether* or *how* stability could recover, only what would follow if it did.
- **Two key parameters cannot be estimated from the data.** These are the connectivity effect on productivity (κ, the "leapfrog" channel the model is built around) and the savings rate. The ensemble spreads across their plausible ranges rather than pretending to know them, and κ's assumed value is deliberately conservative against the literature. Even so, the size of any connectivity-driven effect is an assumption.
- **Connectivity saturates early.** Myanmar's internet-use data stop in 2020, so nothing constrains connectivity after that, and the model saturates it by the mid-2020s in every scenario. This is why "reform push" adds little over "no coup". It is a property of the model, not evidence that connectivity investment does not matter.
- **The structure is small on purpose.** Four stocks and a one-sector Cobb-Douglas economy leave out a great deal:
  - conflict and displacement;
  - sanctions;
  - the informal economy;
  - the exchange rate;
  - remittances;
  - natural-resource rents;
  - climate.

  Every result is conditional on that simplification.
- **The two layers are not fully independent.** COVID is modeled as a persistent loss because the donor countries never returned to trend. That is the same donor information the counterfactual uses, so the agreement between the no-coup scenario and the synthetic control (5.2% apart, within a 10% tolerance) is partly built in.

## The counterfactual has a thin base

- **Six donors.** The synthetic control has only seven units in total, so the smallest attainable p-value is 1/7 ≈ 0.14. Ranking first of seven is the strongest result available, and it is not "statistically significant" in the conventional 5% sense. Amber never claims otherwise.
- **Few donors carry the weight.** Synthetic Myanmar for GDP per capita is two countries (61% Nepal, 39% Cambodia; 1.9 effective donors). Dropping either one keeps a large negative gap, but the size changes: −$359 without Cambodia, −$783 without Nepal.
- **Size depends on specification.** The 2024 GDP gap ranges from −24% (series rebased to 2011) through −26% (default) to −34% (fit ending in 2019). The direction is robust and the magnitude is not, so quote the range.
- **The gap is everything specific to Myanmar after 2021.** That is mainly the coup and its aftermath, but it also includes anything else that hit Myanmar and not its peers in those years. The method cannot separate the two.
- **The combined index has no credible counterfactual.** Myanmar starts below every donor in 2011–2013, and a convex blend cannot go lower than its lowest member. Its pre-coup fit misses by 24% of Myanmar's level. That result is **inconclusive**, which is not the same as showing no effect. The app and the charts say so wherever they show it.
- **The donor pool is a judgment call.** It consists of regional peers with no concurrent 2021+ shock (Sri Lanka is excluded for its 2022 crisis). Other defensible pools exist, and leave-one-out tests how much any single member matters.

## Data gaps and the dark series

- **Several Myanmar series stop reporting.**
  - Secondary enrollment ends after 2018.
  - Internet use ends after 2020.
  - Health expenditure is missing for 2024.
  - Poverty has only three observations (2015–2017).

  By 2024, Myanmar's index rests on six of its nine indicators. Movements where coverage changes are partly composition effects. The charts ring every partial-coverage point, and the scenario charts state the size of the step (about +0.027 in 2024).
- **Nothing is extrapolated, so dark series are absent rather than filled.** This is the honest choice, but it means post-2020 history is measured on a narrower base than earlier years.
- **Interpolation fills interior gaps only.** Interpolated values are flagged, not observed, and the app counts them in its notes.
- **Data revisions.** WDI is revised between vintages. The committed snapshot fixes one vintage, so a refresh can move past values slightly.

## The fiscal-year source caveat

WDI records Myanmar on its **October–September fiscal year** and labels each year by the calendar year holding most of its months. So:

- "2021" includes four months before the February 2021 coup.
- "2020" is entirely pre-coup. It reads −9.1% growth, below every donor and far from the World Bank's contemporaneous +0.5% estimate, so the series has been revised since. No donor blend can reach that value.
- WDI's figures do not match the calendar-year IMF numbers in [the calibration reference](myanmar-precoup-calibration-reference.md) (2020: −9.1% WDI vs −1.2% IMF).

Amber deliberately does **not** splice the two sources: the counterfactual needs every country measured the same way, and mixing conventions would corrupt it. The caveat is printed on every chart of a WDI series.

## The index is one definition of development

- Three pillars, nine indicators, fixed goalposts and a geometric mean are choices, each defensible and none uniquely right. The pillar weights are exposed as controls precisely because they are a value judgment.
- **The innovation pillar measures connectivity adoption only** (internet users and mobile subscriptions), after high-tech exports were excluded for having no structural driver.
- **Some goalposts were seeded from the data and then frozen.** The income ceiling ($6,850) is reached by Vietnam around 2032 at about 6% growth, after which its income score would clip.
- The index says nothing about rights, security, inequality or wellbeing beyond what these nine indicators capture.

---

## Ethics and neutrality

Amber treats the February 2021 coup as a **documented event with measurable consequences**. It takes no partisan stance and is an analytical instrument, not advocacy.

- **Assumptions are controls, not conclusions.** The donor pool, index weights, lever ranges and scenarios are surfaced as settings, so readers can change them and see what follows.
- **Uncertainty is shown, not smoothed away.** Non-credible results are labeled as such and their gaps are withheld. Scenarios are framed as scenarios everywhere. Data gaps are drawn, not hidden.
- **The numbers are aggregates.** GDP per capita and a development index cannot capture the human cost of political violence, displacement or repression. A smaller modeled gap is not a smaller tragedy, and nothing here should be read as weighing lives against output.
- **Neutral, factual language** is the standard for every caption, document and UI string. If you find wording that reads as advocacy for any side, it is a defect: please open an issue.

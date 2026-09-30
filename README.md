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

## Status

🟡 **Early / scaffolding.** Data collection underway.

### Roadmap
- [x] Scope + methodology
- [x] Collect pre-coup plans & baseline trajectory
- [ ] **Data layer** — fetch, cache, and clean the indicator panel (in progress)
- [ ] Past reconstruction + combined index
- [ ] Synthetic-control counterfactual
- [ ] System-dynamics future model
- [ ] Frontend: interactive scenarios + deploy

---

*A portfolio project. The name is a placeholder for a question: what colour is a future that didn't happen?*

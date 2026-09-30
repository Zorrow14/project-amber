# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The repository contains only `README.md`. There's no code, no package manifests and no git repo yet, so there are no build, lint or test commands. Once the backend and frontend are scaffolded, add those commands here, including how to run a single test.

## What Amber is

Amber simulates Myanmar's development in three layers, joined by one combined index:

| Layer | Question | Method |
|-------|----------|--------|
| Past | What actually happened, 2011 to now? | Real indicator series (World Bank WDI, IMF WEO, UNDP HDI) |
| Counterfactual | What if the 2021 coup hadn't happened? | Synthetic control: a weighted blend of donor-pool countries that didn't break in 2021 (Vietnam, Cambodia, others), fitted to real Myanmar before 2021. The gap after 2021 is the estimated loss. |
| Future | What could still happen? | System-dynamics model (PySD) with levers the user can adjust: stability, investment openness, education spending, connectivity |

- **Combined development index:** economy · innovation/tech · human development. Users can adjust the pillar weights. Keep them configurable and don't hardcode them.
- **Conflict data:** ACLED conflict intensity is used to model the divergence after 2021.
- **Counterfactual reference targets:** the civilian government's 2016 Economic Policy and the Myanmar Sustainable Development Plan (2018–2030).

## Planned stack

- Backend: Python, FastAPI (to be deployed on Render)
- Modeling: pandas, statsmodels / scikit-learn, PySD
- Frontend: React with Recharts / Plotly for scenario charts and sliders (to be deployed on Vercel)

## Design principle

The README calls this "an analytical tool, not an argument". Assumptions such as donor-pool choice, index weights and lever ranges should be visible and adjustable. Don't bake in values that decide the conclusion in advance.

## Roadmap position

Scope and the baseline research are done. Next is the **data layer**: fetch, cache and clean the indicator panel. After that come the past reconstruction and the index, then synthetic control, then the system-dynamics model, then the frontend and deployment.

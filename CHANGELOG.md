# Changelog

Amber follows [Semantic Versioning](https://semver.org/). Versions 0.1.0 to 0.5.0 are the build phases, recorded here after the fact: they mark milestones in the commit history and were never tagged. **v1.0.0 is the first tagged release.**

## [Unreleased]

A visual redesign, presentation only. The API, data, behavior and every honesty signal are unchanged; the signals are restyled, not removed.

### Changed
- **A design-token layer.** [`styles/tokens.css`](frontend/src/styles/tokens.css) is the single source for color, type, space, radius, shadow and motion, in light and dark. The palettes are separate:
  - a neutral ramp for the UI;
  - one amber accent;
  - a validated data palette (the treated country as the hero, donors in fixed slots);
  - calm honesty tones.

  See [docs/design-system.md](docs/design-system.md).
- **Inter Variable**, self-hosted (48 kB Latin), with tabular figures on every number and axis.
- **Shared primitives:** `AppShell` (with a light/dark toggle held in memory), `SectionHeader`, `Card`, `ChartFrame`, `ControlPanel`, `StatCallout`, `Banner` and `Pill`, and skeleton loading states.
- **One chart grammar:**
  - no chart-junk;
  - direct end labels with collision avoidance, in place of legends;
  - a single quiet treatment line;
  - one tooltip card with right-aligned tabular values;
  - the hero/neutral split between real Myanmar and anything modeled.
- **Decluttered hierarchy.** One H1 per view, generous section spacing, controls set apart from the charts they drive, and the scenario framing said once per surface.
- The smoke test checks that every chart draws across its plot, and takes full-page screenshots at real layout. It now runs 59 checks.

### Bundle
- JavaScript: about 201.5 → 204.7 kB gzipped (+3.2 kB).
- CSS: 3.3 → 5.4 kB gzipped.
- Font: +48 kB, cached after the first visit.

## [1.0.0] - 2026-10-01

Phase 6: polish, hardening and documentation for the public release. No modeling changed. Every chart and table is byte-identical to 0.5.0.

### Added
- `docs/METHODOLOGY.md`, the design decisions in plain prose, each tied to the `config.py` constant that encodes it.
- `docs/LIMITATIONS.md`, covering the data gaps, source caveats, the thin donor pool and the strong assumptions in the scenario model, plus a note on neutrality.
- `DEPLOY.md`, a runbook for Render and Vercel with a post-deploy smoke checklist and manual QA.
- An explicit cold-start state in the web app. While a sleeping free-tier API wakes up, the app says so, retries on its own and offers "Retry now".
- Loading, error and empty states for every fetch, with friendly, actionable messages and a retry. An error boundary catches a failed view load.
- Accessibility:
  - Visible keyboard focus.
  - A text summary and a "view as table" alternative for every chart.
  - Line patterns and direct labels, so no distinction rests on color alone.
- HTTP caching and compression in the API:
  - The precomputed responses are serialized once at startup and served with a weak `ETag`, so revalidation is a bodiless 304.
  - The GET endpoints send `Cache-Control`.
  - Responses over 1 kB are gzip-compressed.
- Tests:
  - The API makes no outbound network calls.
  - The snapshot loads once per process.
  - Cache headers.
  - The cold-start state.
  - Caveats stay visible through loading transitions.
- `frontend/scripts/smoke.mjs` (`npm run smoke`), a dependency-free Chrome DevTools Protocol smoke test.
  - It loads all four views at 1280 and 375 px, checks the caveats, and drives both live controls.
  - It also captures the README screenshots.
- Frontend performance:
  - The landing view's code loads in parallel with `GET /meta` instead of after it.
  - React and Recharts sit in their own long-lived vendor chunks.
  - Total JavaScript is unchanged at about 201 kB gzipped, but an app-code change now re-downloads about 5 kB instead of 107 kB.

### Changed
- The README is restructured to read in a minute, with badges, screenshots and links to the deeper docs.
- The project plan moved to `docs/`. `CLAUDE.md` is labelled as the conventions file.
- Data attribution is corrected. Every series in the panel comes from World Bank WDI. UNDP and the Sustainable Development Report supply goalpost bounds only.
- Fixed: the "Updating…" status no longer replaces a chart's "Illustrative" caveat badge while a request is in flight.
- Fixed: on phones the top bar no longer stays pinned, which hid an eighth of the screen and the top of scrolled-to sections.
- Fixed: the Makefile's `.PHONY` line was malformed.
- New targets: `make frontend-preview` and `make smoke`.

## [0.5.0] - 2026-10-01

Phase 5: the API and the web app.

- A FastAPI backend serving a committed, hash-checked release snapshot (`data/release/`).
  - Only `/index` and `/simulate` compute on request, and both are cheap forward passes.
  - Nothing is ever refitted on a request.
- A React + TypeScript + Recharts frontend with four views (Overview, Past, Counterfactual, Future).
  - Live pillar-weight and policy-lever controls.
  - Every caveat (coverage, credibility, scenario framing) is rendered beside its series.
- Deploy config for Render (`render.yaml`) and Vercel (`frontend/vercel.json`), and a CI frontend job.

## [0.4.0] - 2026-10-01

Phase 4: future scenarios.

- A hand-written system-dynamics simulator with four stocks (capital, human capital, connectivity, stability) and a connectivity-productivity feedback loop.
  - 13 parameters calibrated to Myanmar's 2011–2024 history.
  - A backtest credibility gate.
- Four configured scenarios and four policy levers, run as a 200-member ensemble. Paired gaps compare scenarios member by member.
- The two parameters the data cannot identify (the connectivity effect κ and the savings rate) are profiled rather than fixed, so the uncertainty bands carry them.
- The index composition is held fixed across history, the counterfactual and projections. Poverty and high-tech exports are kept as history only.

## [0.3.0] - 2026-09-30

Phase 3: the counterfactual.

- A synthetic control with convex, seeded SLSQP weights over six regional donors.
- Placebo tests in space and in time, leave-one-out, and fit-window and rebasing variants.
- A `credible` verdict (pre-period RMSE at most 10% of level) that drives both the captions and the data.

## [0.2.0] - 2026-09-30

Phase 2: past reconstruction and the development index.

- Fixed-goalpost normalization, geometric-mean pillars and a weighted geometric combined index.
- A `coverage` share on every row.
- Static charts committed for the README, and a walkthrough notebook.

## [0.1.0] - 2026-09-30

Phase 1: the data layer.

- World Bank WDI ingestion behind a swappable source, with an on-disk raw cache and provenance sidecars.
- A tidy country-year panel, interior-only interpolation and a coverage report.
- An offline test suite and CI.

[1.0.0]: https://github.com/Zorrow14/project-amber/releases/tag/v1.0.0

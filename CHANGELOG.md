# Changelog

Amber follows [Semantic Versioning](https://semver.org/). Versions 0.1.0 to 0.5.0 are the build phases, recorded here after the fact: they mark milestones in the commit history and were never tagged. **v1.0.0 is the first tagged release.**

## [Unreleased]

This release has two parts:
- **Phase 7:** a historical layer back to 1960, with an illustrative long-run divergence scenario.
- **A visual redesign**, presentation only.

Neither changes phases 1–6. Every existing chart and table re-renders byte-identical, and the 15 existing files in `data/release/` are unchanged; the snapshot gains the four historical tables and a new manifest.

### Added (phase 7: historical arc)
- **`make historical`** ([`amber.historical`](src/amber/historical.py), [`amber.modeling.divergence`](src/amber/modeling/divergence.py)), which is now part of `make models`.
- **Coverage discovery.** Every candidate series is pulled from 1960 and extends back only if Myanmar has at least 20 non-zero pre-2000 observations (`historical_coverage`). On the current vintage six series extend: GDP per capita, GDP growth, life expectancy, under-5 mortality, secondary enrollment and population. The combined index stays 2011+.
- **Three rulers, never spliced:**
  - WDI constant 2015 US$ is the spine.
  - Current-US$ series, and FDI as a share of current-US$ GDP, are excluded and never fetched, because of the kyat-peg artifact.
  - An optional pre-1960 Maddison PPP series is read from a user export ([`data/external/README.md`](data/external/README.md)) and kept under its own id, source tag and axis.
- **Reliability flag.** Every Myanmar observation before 1990 is `low` (`RELIABILITY_LOW_BEFORE`), and charts hatch those years and draw them dotted.
- **The divergence scenario**, which grows Myanmar's anchor-year level at a comparator's actual growth: Thailand by default, or the donor-pool average.
  - It is flagged `scenario_illustrative` on every row, with no p-value or credibility verdict.
  - It is re-run from each sensitivity anchor (1962, 1988, 1990, 2000), because the result turns on the anchor. From 1960 the Thailand path ends 2024 at 1.25× actual; from 1988 onward, below actual.
- **Tables:** `historical`, `historical_coverage`, `historical_divergence`, `historical_divergence_metrics` and `historical_divergence_sensitivity`.
- **Figures:** `historical_gdp_pc.png` and `historical_divergence.png`.
- `ingestion.fetch_series`, the general form of `fetch_indicator`, for non-panel series and comparators. It uses the same cache and schema, and `fetch_indicator`'s behavior is unchanged.
- 33 offline tests (`tests/test_historical.py`), plus METHODOLOGY §6, a LIMITATIONS section and the README's "Historical arc" section.

### Added (motion)
Presentation only: no modeling, endpoint or data-flow change, and the backend is untouched.
- **Line-draw reveal** on every time series, using Recharts' own animation through one helper (`lib/motion.ts`, `drawProps`). Dated markers fade in at their positions. The COVID tint, the low-reliability hatching and the modeling-window bracket never animate.
- **The counterfactual reveal:** real Myanmar draws, then synthetic Myanmar, then the leave-one-out band. A post-treatment gap fill appears for credible outcomes only, so a non-credible gap is never dramatized.
- **A growing fan:** history draws, then the p10–p90 band widens out of it to 2035 and the median draws through it.
- **The year-by-year player** (`usePlayback`, `TimeScrubber`, `DevelopmentPlayer`):
  - On the Future view it shows the combined index, GDP per capita and the three pillar bars, with a tick for actual continuation: World Bank history to 2024, then the scenario median with its p10–p90 range.
  - On the Historical arc it grows the divergence lines year by year.
  - It starts on the final year and never plays on its own. It works with keyboard and touch, and announces the year only when paused.
  - Its tweens (240 ms) stay well under the 500 ms step, so a value is never shown mid-way beside another year's label and range.
- **Count-up stats** (`AnimatedNumber`, `useTween`, `StatCallout`'s `count`). Screen readers read the final value only.
- **Re-tweens:** charts morph between states when the weights or levers change.
- **A quiet view settle:** transform only, never opacity, so no banner is ever drawn faded.
- **Caveats never wait for motion.** Recharts draws dots only after an animation ends, so the hollow coverage rings now sit on their own static layer.
- **Reduced motion** (`useReducedMotion`): no Recharts animation, tweens return the final value, and the CSS rule now also zeroes delays.
- **Tests:**
  - `components/motion.test.tsx` pins that the final state renders immediately under reduced motion, with a control case that does animate.
  - The smoke test now checks that the player steps and keeps its caveat while playing, and adds a reduced-motion pass: 98 checks.
  - `--gif <dir>` captures one settled frame per year for the README asset.

### Bundle (motion)
- JavaScript: 211.0 → 214.7 kB gzipped (+3.7 kB). No new dependency.
- CSS: 5.49 → 5.88 kB gzipped.
- The README GIF is 230 kB, assembled from the `--gif` frames with Pillow at 640 px, 96 colours, 500 ms a year.

### Added (phase 7.5: the historical arc in the API and the app)
- **`GET /historical`** (`countries`, `indicators`; default Myanmar + Thailand, GDP per capita plus Maddison when present) and **`GET /historical/divergence`** (`comparator`). Both are precomputed and never recomputed. Every row carries `source` and `reliability`, and every divergence payload carries `scenario_illustrative: true`, its framing, the anchor sensitivity and a pointer to the Counterfactual view. An unknown country, indicator or comparator is a 422.
- **`/meta.historical`**: window, countries with their role, indicators with their ruler, comparators, markers, the reliability rule, the divergence and sensitivity anchors, and every caveat string, so the frontend hardcodes none of it.
- The four historical tables join `RELEASE_STEMS`. The store refuses a snapshot whose historical rows lost `reliability`/`source` or whose divergence rows are not flagged illustrative.
- **The Historical arc view** (`#/history`):
  - the reconstruction chart, with the pre-1990 low-reliability cue (SVG hatching, the line dotted, a legend key) and the 2011 modeling-window bracket (a separate legend key: "scope, not data quality");
  - a pre-1960 Maddison panel on its own axis, only when the snapshot holds Maddison rows;
  - the divergence panel, with an always-visible "Illustrative scenario, not a causal estimate" banner, a comparator switch, the latest-year ratio and anchor range as stat callouts, and a link to the Counterfactual view.
- A `--chart-hatch` token (light and dark), `hatch` and `bracket` legend swatches, decade ticks for long series, and an optional padded log domain in the shared value axis.
- Tests: 17 API tests (shapes, flags, 422s, `/meta`, startup guards; the historical computations are patched to fail, so nothing recomputes), one component test pinning the divergence banner, and 9 smoke checks per width. The smoke test runs 83 checks.

### Bundle (phase 7.5)
- JavaScript: 204.7 → 211.0 kB gzipped (+6.3 kB). The new view is a lazy 5.4 kB chunk, and the entry grows by 0.2 kB.
- CSS: 5.40 → 5.49 kB gzipped.

### Changed (visual redesign)

A visual redesign, presentation only. The API, data, behavior and every honesty signal are unchanged; the signals are restyled, not removed.

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

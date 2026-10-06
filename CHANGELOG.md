# Changelog

Amber follows [Semantic Versioning](https://semver.org/). Versions 0.1.0 to 0.5.0 are the build phases, recorded here after the fact: they mark milestones in the commit history and were never tagged. **v1.0.0 is the first tagged release.**

## [Unreleased]

This release has these parts:
- **Phase 7:** a historical layer back to 1960, with an illustrative long-run divergence scenario, then its API and app view (7.5).
- **A visual redesign**, presentation only, and a motion layer.
- **English and Burmese**, presentation and `/meta` plumbing only.
- **About, sharing and export**, presentation only: an About landing page, links that reproduce the view, CSV and PNG downloads, a share card, and Sources & citations.

None of these changes phases 1–6. Every existing chart and table re-renders byte-identical, and the 15 existing files in `data/release/` are unchanged; the snapshot gains the four historical tables and a new manifest.

### Added (About, sharing and export)
Presentation only. No modeling, compute or API code changed, and every honesty signal still shows in both languages, at desktop and phone width.
- **About** ([`views/About.tsx`](frontend/src/views/About.tsx)), the new landing page.
  - It is built from the existing primitives (`SectionHeader`, `Card`, `Banner`, `Pill`).
  - It covers the three questions, with links to their views, then "How to read this honestly": the counterfactual is an estimate, not a fact; the future is scenarios, not forecasts. The caveat tags appear as the reader will meet them.
  - Then neutrality, where the data comes from, Sources & citations, and links to the methodology, limitations, code and maker.
  - `VITE_DEFAULT_VIEW=overview` restores the old landing page.
  - About needs nothing from the API: it renders before `/meta` answers (`MetaProvider bootless`), so a cold start is spent reading.
- **Two corrections to the supplied About copy,** so the page matches the repo.
  - "conflict data from ACLED" became "Conflict data, such as ACLED's, is not used". ACLED is not an input; see LIMITATIONS.
  - "the UN" became "many of them compiled by UN agencies". Every indicator comes from WDI; UN agencies compile many of them, and UNDP supplies only cited goalposts.
  - The Past card links to both Past (2011+) and the Historical arc (1960+), so "back to 1960" holds.
- **The Burmese About copy is a draft, flagged as one.**
  - Every `views.about.*` and `sources.entries.*` key is `human-verify`.
  - Each is listed with an intent note in table C of [`docs/i18n-review.md`](docs/i18n-review.md).
  - In Burmese, each honesty passage shows a draft note until it is signed off, so the copy is never presented as final.
- **Shareable URL state** ([`lib/url.ts`](frontend/src/lib/url.ts), [`context/route.tsx`](frontend/src/context/route.tsx)).
  - The URL holds:
    - `view`;
    - `scenario`, `levers` and `series` (Future);
    - `weights` (Past);
    - `comparator` (Historical arc);
    - `lang`.
  - Only values that differ from their defaults are written, exactly, so a reloaded link rebuilds the same state.
  - Values are checked against `/meta` when read.
  - Opening a view pushes a history entry; a control change uses `history.replaceState`. Nothing is stored.
  - The routing moved from the hash to the query. Old `#/view` links still open, and are rewritten.
  - The header gains a labelled copy-link button that announces its result.
- **Downloads** ([`lib/export.ts`](frontend/src/lib/export.ts), loaded on first use, no dependencies). Every `ChartFrame` gains **CSV** and **PNG** buttons.
  - The CSV holds the raw values behind the chart's table, with coverage or reliability columns. Leading `#` lines carry the title, caveat badge, callout, notes, source, a dated link back to the exact view, and the WDI licence.
  - The PNG redraws the plot's SVG on a canvas at 2×, with the same words around it. The canvas draws the text itself in the page's fonts, because an SVG drawn as an image can paint its web-font text late or not at all. So Burmese exports correctly.
- **Share card:**
  - Open Graph and Twitter `summary_large_image` tags, whose description is the opening of `PROJECT_FRAMING`, word for word (`tests/test_share_card.py`);
  - a static [`public/og-image.png`](frontend/public/og-image.png) (1200 × 630) of the brand, the headline and the GDP chart, captured by `npm run smoke -- --og`;
  - absolute URLs from `VITE_SITE_URL`.
- **Sources & citations** ([`components/Sources.tsx`](frontend/src/components/Sources.tsx), [`lib/sources.ts`](frontend/src/lib/sources.ts)) at `/#sources`, linked from every footer and from under every chart.
  - It groups the sources by role:
    - data in the app: WDI (CC BY 4.0) and Maddison;
    - standards cited: UNDP and SDSN;
    - a cross-check: the IMF;
    - a scenario direction: the MSDP;
    - methods: Abadie, Diamond and Hainmueller (2010), and Czernich et al. (2011);
    - not used: ACLED and the published HDI.
  - Citations keep their published English form (`lang="en"`).
- **Tests:**
  - Frontend, 25 → 45:
    - About is the default route and renders before `/meta`;
    - its honesty copy shows in both languages, with draft notes in Burmese;
    - its links and sources are right;
    - the URL schema round-trips, legacy hashes still work, and malformed values fall back;
    - the Future and Past controls hydrate from a URL, and changes rewrite it in place;
    - the CSV holds the loaded series, its coverage and its caveats;
    - every About key is flagged.
  - Backend, 316 → 319: the share card (`tests/test_share_card.py`).
  - Smoke, 220 → 281 checks: the landing page, the About honesty copy and its Burmese draft notes, URL hydration and in-place updates, the CSV and PNG downloads (English and Burmese), the footer's sources link, the share card as served, and text running off the edge at 375 px.

### Bundle (About, sharing and export)
Measured the same way before and after (gzip level 9):
- **First load on the landing page:** 201.4 kB of JavaScript (the Overview, before) → 88.8 kB (About). Recharts now loads only when a chart view opens.
- **First load on a chart view:** about 4.6 kB more, for example the Overview at 201.4 → 206.0 kB.
- **All chunks:** 227.9 → 241.9 kB. Of the difference:
  - 3.1 kB is the export code, fetched on the first download;
  - 3.1 kB is the larger Burmese catalog, fetched only in Burmese;
  - 2.4 kB is the About view.
- **CSS:** 6.18 → 6.67 kB gzipped.
- **Share image:** `og-image.png`, 74 kB, fetched only by link-preview crawlers.

### Added (internationalization: English + Burmese)
Presentation and light plumbing only. No modeling, index, synthetic-control or divergence logic changed, every table and figure re-renders byte-identical, and the English output is unchanged.
- **A small typed i18n layer** ([`frontend/src/i18n/`](frontend/src/i18n/)) instead of react-i18next.
  - The app needs two locales and `{placeholder}` interpolation, nothing more; Burmese has no plural forms.
  - It costs about 1 kB rather than ~20 kB gzipped, and keys are typed from `en.json`, so tsc rejects a key that does not exist.
- **Locale files:** `en.json` and `my.json`, namespaced `app`, `nav`, `banners`, `errors`, `controls`, `honesty`, `charts`, `meta` and `views`.
  - No user-visible string is left in a component; screen-reader summaries and table captions are included.
  - `my.json` is its own lazily loaded chunk.
- **The language toggle:** EN / မြန်မာ in the header, a two-button group with `aria-pressed`, each language named in its own script and `lang`.
  - The initial language follows `navigator.languages` (Accept-Language), falling back to English.
  - The choice is held in memory, with no storage.
  - `<html lang>` and the document title follow the language on screen.
- **Data labels in both languages.** [`src/amber/i18n.py`](src/amber/i18n.py) maps every English display string the API exposes to Burmese.
  - It covers countries, indicators, pillars, levers, scenarios, outcomes, model series, regime markers, comparators and every caveat.
  - The map is keyed by the English verbatim, so an edited English caveat fails startup until it is re-translated.
  - `/meta` gains `locales`, `default_locale`, `translation_review_pending` and an `_i18n: {en, my}` twin beside every display field.
  - Caveat text in the other responses gets twins too: not-credible messages, the phase 3 check reasons, the custom-scenario label, the historical and divergence notes and banner text, and the markers. The English fields and every number are unchanged.
  - The custom-scenario label, SC-check reasons and divergence anchor note move to config templates with the same English text.
- **`localize`:** `useApi` replaces each display field with its twin for the active language, so views read `c.name` as before and Burmese mode cannot show an English series name.
- **Burmese type:**
  - Noto Sans Myanmar, self-hosted through `@fontsource-variable/noto-sans-myanmar`, with only its Myanmar face registered.
  - Under `lang="my"` the tokens raise the small sizes a step, add leading for stacked glyphs (display 1.05 → 1.5, prose 1.55 → 1.85) and zero the tracking.
  - Unicode only, never Zawgyi.
- **Numerals stay Western** in both languages; the formatters are pinned to `en-US`. Ordinals follow CLDR: "7th of 7" / "7 ခုအနက် အဆင့် 7".
- **Honesty about the translation.**
  - The Burmese is a machine-assisted first pass.
  - The honesty strings and the political-event labels are flagged `human-verify` (`my.json` `_review`; `i18n.REVIEW`) and listed in [`docs/i18n-review.md`](docs/i18n-review.md) with a glossary.
  - The Burmese footer says the review is pending until both lists are cleared.
- **Banners name their kind** (`data-banner`), so tooling and tests read them in any language.
- **Tests:**
  - Backend: `tests/test_i18n.py` (12) and three locale tests in `tests/test_api.py`. Every `_i18n` twin in every response matches its English and is Unicode Burmese with Western digits.
  - Frontend: catalog parity, placeholders, review flags, Unicode and digits; browser-language detection; `localize`; a language switch through the real header; and the not-credible, scenario and illustrative banners rendered in Burmese, with scenario and lever names from `/meta`.
  - The smoke test runs every view again in Burmese at both widths, by Accept-Language: 220 checks. It covers the page language, the font actually painted, Western digits, no English names, no clipped text, the toggle, and every caveat in Burmese.

### Bundle (internationalization)
Measured the same way before and after (all JavaScript chunks, gzip level 9):
- **JavaScript:** 207.5 → 222.1 kB gzipped.
  - Of that, 9.1 kB is the Burmese catalog, fetched only when Burmese is chosen.
  - An English reader's JavaScript grows by about 5.5 kB: the English catalog and the i18n layer.
- **CSS:** 5.71 → 6.04 kB gzipped.
- **Font:** the Noto Sans Myanmar Myanmar-script face, 154 kB woff2, downloaded only when Burmese text is on screen.
- **Dependencies:** `@fontsource-variable/noto-sans-myanmar` is the only new one, and it has no code.

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

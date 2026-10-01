# Deploying Amber

This is a step-by-step guide to putting Amber online: the **API on Render** and the **web app on Vercel**, both on free plans. It assumes you have never deployed this before. Plan on about 20 minutes. Most of that is waiting for the first builds.

Nothing here needs a secret. The API serves a committed data snapshot, so it never calls the World Bank or any other service, and no keys or tokens are involved.

**Contents**

0. [Before you start](#0-before-you-start)
1. [Deploy the API on Render](#1-deploy-the-api-on-render)
2. [Deploy the web app on Vercel](#2-deploy-the-web-app-on-vercel)
3. [Connect them (CORS)](#3-connect-them-cors)
4. [Post-deploy smoke checklist](#4-post-deploy-smoke-checklist)
5. [Manual QA checklist](#5-manual-qa-checklist)
6. [Repository finishing touches](#6-repository-finishing-touches)
7. [Day-2 operations](#7-day-2-operations)
8. [Troubleshooting](#8-troubleshooting)

Also: [Appendix: the local end-to-end check](#appendix-the-local-end-to-end-check).

---

## 0. Before you start

You need:

- the repository pushed to GitHub (`main`, including the committed `data/release/` folder);
- a free [Render](https://render.com) account and a free [Vercel](https://vercel.com) account, both signed in with GitHub so they can see the repository.

Optionally, run the [local end-to-end check](#appendix-the-local-end-to-end-check) first. If it passes on your machine, the deploy will very likely work too.

**Environment variables at a glance**

| Where | Variable | Value | Notes |
|---|---|---|---|
| Render | `AMBER_DATA_SOURCE` | `release` | Set by `render.yaml`. Serves `data/release/`. |
| Render | `AMBER_CORS_ORIGINS` | your Vercel URL, e.g. `https://amber-xyz.vercel.app` | Set in step 3. Comma-separate several. No trailing slash. |
| Render | `AMBER_LOG_LEVEL` | `INFO` | Set by `render.yaml`. |
| Render | `PYTHON_VERSION` | `3.12.8` | Set by `render.yaml`. |
| Vercel | `VITE_API_BASE_URL` | your Render URL, e.g. `https://amber-api.onrender.com` | Baked in **at build time**, so a change needs a redeploy. |

Templates for both sides are in [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example).

---

## 1. Deploy the API on Render

[`render.yaml`](render.yaml) is a Render *Blueprint*: it describes the `amber-api` web service, so there is almost nothing to type.

1. In the Render dashboard, choose **New → Blueprint**.
2. Pick this repository and branch `main`. Render finds `render.yaml` and shows one service, **amber-api** (free plan).
3. Render asks for **`AMBER_CORS_ORIGINS`**, because the file marks it `sync: false`. You don't have the Vercel URL yet, so enter `http://localhost:5173` for now. You'll replace it in step 3.
4. Click **Apply**. The first build installs the package (`pip install -e .`) and takes a few minutes.
5. When the service shows **Live**, copy its URL from the top of the service page, e.g. `https://amber-api.onrender.com`.
6. Check it in a browser or with curl:

   ```bash
   curl https://amber-api.onrender.com/health
   ```

   You should see `"status": "ok"` and `"source": "release"`, with the snapshot's `built_at` date and commit. The interactive API docs are at `/docs`.

> **The free plan sleeps.** After about 15 minutes with no traffic, Render stops the service, and the next request takes up to a minute while it starts again. The web app handles this. It shows *"Waking the server - this can take up to a minute"*, retries on its own, and offers *Retry now*. A slow first load after a quiet spell is expected, not broken. A paid instance never sleeps.

---

## 2. Deploy the web app on Vercel

1. In the Vercel dashboard, choose **Add New → Project** and import this repository.
2. Set **Root Directory** to **`frontend`**. This is the one setting that matters.
   - Vercel then reads [`frontend/vercel.json`](frontend/vercel.json) and detects Vite.
   - The install command is `npm ci`, the build command `npm run build` and the output directory `dist`. Leave them as detected.
3. Under **Environment Variables**, add `VITE_API_BASE_URL` = the Render URL from step 1.5. Use no trailing slash, e.g. `https://amber-api.onrender.com`. Apply it to Production and Preview.
4. Click **Deploy**. When it finishes, copy the production URL, e.g. `https://amber-xyz.vercel.app`.

Routing uses the URL hash (`#/future`), so no rewrites or redirects are needed.

If you open the site now it will say the API is not responding. That is expected until step 3.

---

## 3. Connect them (CORS)

The API only answers browsers from origins it knows.

1. In Render, open **amber-api → Environment** and set **`AMBER_CORS_ORIGINS`** to your Vercel production URL, e.g. `https://amber-xyz.vercel.app`.
   - Use the exact scheme and host, with no trailing slash and no path.
   - To allow more than one origin (a custom domain, or a fixed preview alias), comma-separate them: `https://amber-xyz.vercel.app,https://amber.example.com`.
2. Save. Render redeploys with the new value; wait for **Live**.
3. Reload the Vercel site. All five views should load.

Vercel preview deployments get a new URL each time, so previews can't reach the API unless you add their URL too. That is fine: test previews locally, and treat the production URL as the demo.

---

## 4. Post-deploy smoke checklist

Replace the two URLs with yours.

```bash
API=https://amber-api.onrender.com
APP=https://amber-xyz.vercel.app

curl -s $API/health                                  # "status": "ok", "source": "release"
curl -s -D - -o /dev/null $API/meta | grep -i -E "etag|cache-control"  # ETag + Cache-Control: public, max-age=600
curl -s -o /dev/null -w "%{http_code}\n" "$API/index?weights=economy=-1"   # 422, not 500
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/simulate \
     -H "Content-Type: application/json" -d '{"levers":{"fdi_openness":9}}' # 422 (out of range)
curl -s -D - -o /dev/null -H "Origin: $APP" $API/health | grep -i access-control-allow-origin  # echoes $APP
```

Then run the automated browser check against the live site. It needs Node 22+ and Chrome, Chromium or Edge on your machine:

```bash
cd frontend
npm ci
npm run smoke -- --url $APP
```

It loads all five views at desktop and phone width, checks that nothing overflows and that every caveat is visible, moves a weight slider and a lever, and checks that the API answered and the chart redrew. It also checks that every chart draws across its plot. It should end with `59/59 checks passed`. If the API was asleep, the first view simply takes longer; the script waits up to two minutes per view.

- [ ] `/health` reports `source: release` and the expected snapshot date
- [ ] `/meta` carries `ETag` and `Cache-Control`
- [ ] Bad input returns 422 with a readable `detail`
- [ ] CORS echoes the Vercel origin
- [ ] `npm run smoke -- --url $APP` passes
- [ ] The footer of the app shows the same snapshot date and commit as `/health`

---

## 5. Manual QA checklist

These are the things worth checking by hand once, on the live site.

**Phone** (a real one if you can, or the browser's device toolbar at 375 px)
- [ ] Every view reads top to bottom with no sideways scrolling, and charts fit the screen.
- [ ] Sliders move by touch, and the scenario cards select by tap.
- [ ] The tabs scroll sideways if they don't fit.

**Cold start**
- [ ] Leave the site idle for 20+ minutes, or suspend the Render service and resume it.
- [ ] Open the app in a fresh tab. Within a few seconds it shows *"Waking the server - this can take up to a minute"* with an elapsed-time counter and *Retry now*, then loads on its own.
- [ ] No blank screen, no raw error text.

**Honesty: a `credible = false` path**
- [ ] On **Counterfactual**, the *Combined development index* section opens with the red *"Not a credible effect estimate"* banner.
- [ ] Its three charts are badged *Illustrative only*, and its gap reads *"is not reported"*. No number is stated as an effect.
- [ ] *Real GDP per capita*, which is credible, states its gap, with no banner.
- [ ] On **Future**, *"Scenarios, not forecasts"* is always shown and the chart carries *"Scenario, not a forecast"*. While a lever change re-runs, *Updating…* appears **beside** that badge, never in place of it.
- [ ] On **Past** and **Future**, post-2018 Myanmar points are hollow rings, and the legend explains them.

**Bad input: a 422**
- [ ] On **Past**, drag all three pillar weights to 0. A notice reads *"These weights cannot produce an index"* with the API's reason, and the chart keeps the last valid weighting.
- [ ] Reset to equal, and the notice clears.

**Keyboard and screen reader**
- [ ] Press Tab from the top of the page. *Skip to content* appears first, and every control shows a visible focus ring.
- [ ] Arrow keys move the sliders and the scenario radios.
- [ ] Each chart has a *View the data as a table* disclosure. A screen reader announces a one-paragraph summary for each chart.

**Dark mode**
- [ ] Switch the OS to dark. The app follows, and text and lines stay legible.

---

## 6. Repository finishing touches

These settings can only be changed on GitHub by you.

**About box.** On the repository page, click the gear next to *About*.

- **Description:**
  > Myanmar's development, past, counterfactual and future: a synthetic-control estimate of the 2021 coup's cost and an interactive system-dynamics scenario model. An analytical instrument, not an argument.
- **Website:** your Vercel URL.
- **Topics:**
  `synthetic-control` `counterfactual` `causal-inference` `system-dynamics` `scenario-analysis` `development-economics` `myanmar` `world-bank` `data-visualization` `fastapi` `react` `typescript` `recharts` `python`

**Live-demo link in the README.** Replace the placeholder near the top of [`README.md`](README.md):

```markdown
**[Live demo](https://amber-xyz.vercel.app)** · API: [amber-api.onrender.com/docs](https://amber-api.onrender.com/docs)
```

**Tag the release.** After the Phase 6 work is merged to `main`:

```bash
git checkout main && git pull
git tag -a v1.0.0 -m "Amber 1.0.0"
git push origin v1.0.0
```

Then, on GitHub, go to **Releases → Draft a new release**, choose `v1.0.0`, and paste the 1.0.0 section of [`CHANGELOG.md`](CHANGELOG.md).

**Refresh the screenshots against the live site** (optional). The committed ones were captured from a local run of the same build:

```bash
cd frontend && npm run smoke -- --url $APP --screenshots ../docs/images
git add ../docs/images && git commit -m "Refresh screenshots from the live site"
```

---

## 7. Day-2 operations

**Pushing code.** Both services redeploy on every push to `main`: Render because `render.yaml` sets `autoDeploy`, and Vercel by default.

**Refreshing the data.** The API serves exactly what is committed in `data/release/`, and refuses to start if a file fails its manifest hash.

```bash
make panel && make index && make models   # rebuild the tables (make refresh re-pulls WDI)
make release                              # copy them into data/release + manifest.json
make test                                 # the API tests run against the new snapshot
git add data/release reports/figures && git commit -m "Refresh the data snapshot"
git push                                  # Render redeploys with the new data
```

Never edit `data/release/` by hand. Regenerate it.

**Rolling back.** In Render, open **amber-api → Events** and click *Rollback* on an earlier deploy. In Vercel, open **Deployments**, choose an earlier one, then **Promote to Production**.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| The app says *"The Amber API is not responding"* after the waking period | `VITE_API_BASE_URL` was missing at build time, so the app calls `http://localhost:8000` | Set it in Vercel (step 2.3) and **redeploy**. Vite bakes it in at build time. |
| Browser console: *blocked by CORS policy* | `AMBER_CORS_ORIGINS` doesn't exactly match the site's origin | Copy the origin from the address bar (scheme + host, no slash) into Render (step 3) |
| Render deploy fails at startup with `DataUnavailableError` | `data/release/` is missing, partial or edited by hand | Run `make release`, commit `data/release/`, push |
| Render build fails installing dependencies | Python version drift | Keep `PYTHON_VERSION` at a 3.11+ release that has wheels for pandas and scipy (3.12.x) |
| A view shows *"This view could not be shown"* right after a redeploy | The browser holds the old page and asks for code chunks that no longer exist | Click *Reload the page* |
| First load takes ~a minute | Render free-tier cold start | Expected. See step 1. A paid instance never sleeps. |

---

## Appendix: the local end-to-end check

This is how the release was verified before deploy. It proves that a fresh clone runs the whole app from committed files only.

```bash
git clone https://github.com/Zorrow14/project-amber.git amber-check && cd amber-check
python -m venv .venv && .venv/bin/pip install -e ".[dev]"     # Windows: .venv\Scripts\...
.venv/bin/python -m pytest                                    # 301 passed; no network needed

# Terminal 1 - the API on the committed snapshot (data/raw and data/processed are empty)
AMBER_CORS_ORIGINS=http://localhost:4173 .venv/bin/python -m uvicorn amber.api.main:app --port 8000

# Terminal 2 - the production build of the web app
cd frontend && npm ci && npm test && npm run build && npx vite preview --port 4173

# Terminal 3 - the browser smoke test
cd frontend && npm run smoke -- --url http://localhost:4173     # 98/98 checks passed
```

`tests/test_api.py::test_the_api_serves_the_release_with_no_outbound_connections` blocks every non-loopback socket and then starts the API and calls every endpoint. That makes "zero World Bank calls" a tested property, not a promise.

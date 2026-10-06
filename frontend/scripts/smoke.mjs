#!/usr/bin/env node
/**
 * Browser smoke test for the running app, over the Chrome DevTools Protocol -
 * no dependencies beyond Node 22+ and an installed Chrome, Chromium or Edge.
 *
 * For every view, at desktop (1280 px) and phone (375 px) width, it checks that
 * the view loads without an error, that nothing overflows the viewport sideways,
 * and that the caveats the data carries are visible: hollow partial-coverage
 * points, the not-credible banner, the "scenarios, not forecasts" framing. It
 * then moves a pillar-weight slider and a policy lever and checks that /index
 * and /simulate were called and the chart redrew.
 *
 * Then it runs every view again in Burmese, chosen the way a reader's browser
 * would (Accept-Language: my-MM): the page language, the Burmese font actually
 * used to paint the text, no English series name left on screen, Western digits,
 * no clipped text, and every caveat - in Burmese - still visible.
 *
 * It also checks that About is the landing page, that a shared URL rebuilds the
 * view it names, that the CSV and PNG downloads arrive (with the caveat in the
 * CSV), and that the served page carries its link-preview card.
 *
 *   npm run build && npx vite preview --port 4173 &   # plus the API on :8000
 *   node scripts/smoke.mjs --url http://localhost:4173
 *   node scripts/smoke.mjs --url https://<your-app>.vercel.app --screenshots ../docs/images
 *
 * Options: --url (default http://localhost:4173), --browser <path> (or $BROWSER),
 * --screenshots <dir> (writes the README images: app-about, app-overview, app-future,
 * app-mobile, app-history, app-history-divergence, app-my-overview, app-my-mobile),
 * --all (with --screenshots: also a full-page shot of every view at both widths, for QA),
 * --exports <dir> (keep the downloaded CSV and PNG files there, for inspection),
 * --og <file> (write the 1200 x 630 link-preview image, public/og-image.png),
 * --timeout <ms per view>.
 * Exits non-zero if any check fails.
 */
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

/** `--key value` and bare `--flag` pairs; values may contain anything, spaces included. */
function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i].replace(/^--/, "");
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) parsed[key] = "true";
    else parsed[key] = argv[++i];
  }
  return parsed;
}
const args = parseArgs(process.argv.slice(2));

/** The Burmese catalog, for the strings the Burmese pass expects on screen. */
const MY = JSON.parse(readFileSync(new URL("../src/i18n/locales/my.json", import.meta.url), "utf8"));
const my = (key) => key.split(".").reduce((node, part) => node[part], MY);
const APP_URL = (args.url ?? "http://localhost:4173").replace(/\/+$/, "");
const VIEW_TIMEOUT = Number(args.timeout ?? 120_000);
const SHOTS = args.screenshots ? resolve(args.screenshots) : null;
const ALL_SHOTS = args.all === "true";
const EXPORTS = args.exports ? resolve(args.exports) : null;

/** A view's URL: a distinct `smoke` tag makes every navigation a fresh page load. */
const viewUrl = (tag, view, extra = "") => `${APP_URL}/?smoke=${tag}${view ? `&view=${view}` : ""}${extra}`;

const CANDIDATES = [
  process.env.BROWSER,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/microsoft-edge",
];
const BROWSER = args.browser ?? CANDIDATES.find((path) => path && existsSync(path));
if (!BROWSER) {
  console.error("No Chrome, Chromium or Edge found; pass --browser <path> or set $BROWSER.");
  process.exit(2);
}

// ---------------------------------------------------------------- CDP plumbing

async function launch() {
  const profile = mkdtempSync(join(tmpdir(), "amber-smoke-"));
  const child = spawn(
    BROWSER,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  const portFile = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 100 && !existsSync(portFile); i++) await sleep(100);
  const [port] = readFileSync(portFile, "utf8").split("\n");
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find((t) => t.type === "page");
  const close = () => {
    child.kill();
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      // the browser may still hold the profile on Windows; it is in tmp
    }
  };
  return { wsUrl: page.webSocketDebuggerUrl, close };
}

function connect(wsUrl) {
  const socket = new WebSocket(wsUrl);
  let nextId = 0;
  const pending = new Map();
  const listeners = new Set();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id != null && pending.has(message.id)) {
      const { resolve: ok, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else ok(message.result);
    } else if (message.method) {
      for (const listener of listeners) listener(message);
    }
  });
  const ready = new Promise((ok, reject) => {
    socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  return {
    ready,
    send(method, params = {}) {
      const id = ++nextId;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((ok, reject) => pending.set(id, { resolve: ok, reject }));
    },
    on(listener) {
      listeners.add(listener);
    },
    once(method) {
      return new Promise((ok) => {
        const listener = (message) => {
          if (message.method !== method) return;
          listeners.delete(listener);
          ok(message.params);
        };
        listeners.add(listener);
      });
    },
    close() {
      socket.close();
    },
  };
}

// ---------------------------------------------------------------- the checks

/** The longest first-view reveal (draw, then the band) plus margin. */
const ANIMATION_SETTLE_MS = 2400;

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900, deviceScaleFactor: 1, mobile: false },
  { name: "mobile", width: 375, height: 812, deviceScaleFactor: 2, mobile: true },
];

/** In-page assertions per view. Each returns [label, passed, detail]. */
const VIEW_CHECKS = {
  // Loaded from a URL that names no view: About is the landing page.
  about: `[
    ["About is the landing view", document.querySelector("main h1")?.textContent === "About Amber"
      && document.querySelector(".nav__link[aria-current=page]")?.textContent === "About", location.search],
    ["the honesty banner is visible", [...document.querySelectorAll("[data-banner=framing]")].some((el) =>
      el.textContent.includes("not a crystal ball") && visible(el)), ""],
    ["both honesty points are stated", visible(textEl("an estimate, not a fact")) && visible(textEl("scenarios, not forecasts")), ""],
    ["the caveat tags are shown", [...document.querySelectorAll(".about__caveats .pill")].filter(visible).length === 4, ""],
    ["sources and citations are listed", visible(document.getElementById("sources")) && document.querySelectorAll(".source").length >= 10,
      document.querySelectorAll(".source").length + " sources"],
    ["the code and maker links resolve", ["https://github.com/Zorrow14/project-amber", "https://htet-aung-lwin-portfolio.vercel.app/"]
      .every((href) => [...document.querySelectorAll(".about__learn a")].some((a) => a.href === href)), ""],
    ["the copy-link control is labelled", visible(document.querySelector("button[aria-label='Copy a link to this view']")), ""],
  ]`,
  overview: `[
    ["framing: 'analytical instrument' is shown", visible(textEl("analytical instrument")), ""],
    ["the GDP divergence chart rendered", document.querySelectorAll("figure .recharts-line").length >= 7, ""],
  ]`,
  history: `[
    ["the illustrative-scenario banner is visible", [...document.querySelectorAll("[role=note]")].some((el) =>
      el.textContent.includes("Illustrative scenario, not a causal estimate") && visible(el)), ""],
    ["the divergence chart carries its 'Illustrative scenario' badge", [...document.querySelectorAll("[data-caveat]")].some((el) =>
      el.textContent === "Illustrative scenario" && visible(el)), ""],
    ["the pointer to the Counterfactual view is visible", visible(document.querySelector("[role=note] a[href$='view=counterfactual']")), ""],
    ["the latest-year ratio is stated", visible(textEl("illustrative path ÷ actual")), ""],
    ["the low-reliability key is visible", visible(textEl("Hatched: low-reliability years")), ""],
    ["the modeling-window key is visible", visible(textEl("scope, not data quality")), ""],
    ["low-reliability years are hatched", document.querySelectorAll("figure [fill^='url(#hatch']").length >= 2,
      document.querySelectorAll("figure [fill^='url(#hatch']").length + " hatched areas"],
    ["the modeling-window bracket is drawn", document.querySelectorAll("figure .window-bracket").length >= 2, ""],
    ["no text calls it a counterfactual estimate", !document.body.textContent.toLowerCase().includes("counterfactual estimate"), ""],
  ]`,
  past: `[
    ["coverage legend 'Partial indicator coverage' is visible", visible(textEl("Partial indicator coverage")), ""],
    ["hollow partial-coverage points are drawn", document.querySelectorAll("figure circle[r='4']").length > 0,
      document.querySelectorAll("figure circle[r='4']").length + " rings"],
    ["the coverage note is visible", visible(textEl("rests on")), ""],
  ]`,
  counterfactual: `[
    ["a not-credible banner is visible", [...document.querySelectorAll("[role=alert]")].some((el) =>
      el.textContent.includes("Not a credible effect estimate") && visible(el)), ""],
    ["its charts are badged 'Illustrative only'", [...document.querySelectorAll("[data-caveat]")].some((el) =>
      el.textContent === "Illustrative only" && visible(el)), ""],
    ["its gap is withheld, not stated as an effect", visible(textEl("gap is not reported")), ""],
    ["a credible outcome states its gap", visible(textEl(" gap: ")), ""],
  ]`,
  future: `[
    ["'Scenarios, not forecasts' is visible", visible(textEl("Scenarios, not forecasts")), ""],
    ["the chart carries its scenario badge", [...document.querySelectorAll("[data-caveat]")].some((el) =>
      /Scenario, not a forecast|Illustrative dynamics/.test(el.textContent) && visible(el)), ""],
    ["hollow partial-coverage history points are drawn", document.querySelectorAll("figure circle[r='4']").length > 0, ""],
    ["the composition-step note is visible", visible(textEl("composition step")), ""],
    ["the year-by-year player is shown", visible(textEl("year by year")), ""],
    ["the player carries its scenario badge", [...document.querySelectorAll(".player [data-caveat]")].some((el) =>
      /Scenario, not a forecast|Illustrative dynamics/.test(el.textContent) && visible(el)), ""],
    ["every chart offers labelled CSV and PNG downloads", [...document.querySelectorAll("figure.chart-frame")].every((figure) =>
      visible(figure.querySelector("button[aria-label='Download this chart as a PNG image']"))), ""],
  ]`,
};

/** The same caveats, in Burmese: each must still be on screen, in the reader's language. */
const BURMESE_CHECKS = {
  about: `[
    ["the honesty banner is in Burmese", [...document.querySelectorAll("[data-banner=framing]")].some((el) =>
      el.textContent.includes(${JSON.stringify(my("views.about.estimateLead"))})
      && el.textContent.includes(${JSON.stringify(my("views.about.scenarioLead"))}) && visible(el)), ""],
    ["each draft honesty passage says it is a draft translation", (() => {
      const drafts = [...document.querySelectorAll(".about__draft")];
      return drafts.length === 3 && drafts.every((el) => visible(el) && el.textContent === ${JSON.stringify(my("views.about.draft"))});
    })(), document.querySelectorAll(".about__draft").length + " draft markers"],
    ["the caveat tags are in Burmese", [...document.querySelectorAll(".about__caveats .pill")].some((el) =>
      el.textContent === ${JSON.stringify(my("honesty.scenarioBadge"))} && visible(el)), ""],
    ["citations stay in English, marked as English", [...document.querySelectorAll(".source__citation")].every((el) => el.lang === "en"), ""],
  ]`,
  overview: `[
    ["the project framing is shown, in Burmese", (() => { const el = document.querySelector(".framing"); return visible(el) && /[\u1000-\u104f]/u.test(el.textContent); })(), ""],
    ["the GDP divergence chart rendered", document.querySelectorAll("figure .recharts-line").length >= 7, ""],
  ]`,
  history: `[
    ["the illustrative-scenario banner is visible", [...document.querySelectorAll("[data-banner=framing]")].some((el) =>
      el.textContent.includes(${JSON.stringify(my("honesty.illustrativeScenarioTitle"))}) && visible(el)), ""],
    ["the divergence chart carries its 'illustrative scenario' badge", [...document.querySelectorAll("[data-caveat]")].some((el) =>
      el.textContent === ${JSON.stringify(my("honesty.illustrativeScenario"))} && visible(el)), ""],
    ["the pointer to the Counterfactual view is visible", visible(document.querySelector("[data-banner=framing] a[href*='view=counterfactual']")), ""],
    ["the low-reliability key is visible", visible(textEl(${JSON.stringify(my("honesty.hatched"))})), ""],
    ["the modeling-window key is visible", visible(textEl(${JSON.stringify(my("honesty.windowKey").replace("{year}", "2011"))})), ""],
    ["low-reliability years are hatched", document.querySelectorAll("figure [fill^='url(#hatch']").length >= 2, ""],
    ["the modeling-window bracket is drawn", document.querySelectorAll("figure .window-bracket").length >= 2, ""],
  ]`,
  past: `[
    ["the coverage key is visible", visible(textEl(${JSON.stringify(my("honesty.partialCoverage"))})), ""],
    ["hollow partial-coverage points are drawn", document.querySelectorAll("figure circle[r='4']").length > 0, ""],
    ["the partial-coverage pill is visible", visible(document.querySelector(".chart-frame__callout .pill")), ""],
  ]`,
  counterfactual: `[
    ["a not-credible banner is visible", [...document.querySelectorAll("[data-banner=credibility]")].some((el) =>
      el.textContent.includes(${JSON.stringify(my("honesty.scNotCredibleTitle"))}) && visible(el)), ""],
    ["its charts are badged 'illustrative only'", [...document.querySelectorAll("[data-caveat]")].some((el) =>
      el.textContent === ${JSON.stringify(my("honesty.illustrativeOnly"))} && visible(el)), ""],
    ["its gap is withheld, not stated as an effect", visible(textEl("ကွာဟချက်ကို မဖော်ပြပါ")), ""],
  ]`,
  future: `[
    ["'scenarios, not forecasts' is visible", [...document.querySelectorAll("[data-banner=framing]")].some((el) =>
      el.textContent.includes(${JSON.stringify(my("honesty.scenarioTitle"))}) && visible(el)), ""],
    ["the chart carries its scenario badge", [...document.querySelectorAll("figure [data-caveat]")].some((el) =>
      [${JSON.stringify(my("honesty.scenarioBadge"))}, ${JSON.stringify(my("honesty.illustrativeDynamics"))}].includes(el.textContent) && visible(el)), ""],
    ["the player carries its scenario badge", [...document.querySelectorAll(".player [data-caveat]")].some((el) => visible(el)), ""],
    ["hollow partial-coverage history points are drawn", document.querySelectorAll("figure circle[r='4']").length > 0, ""],
  ]`,
};

/** English display names that must not survive into Burmese mode where series and views are named. */
const ENGLISH_NAMES = [
  "Myanmar", "Vietnam", "Cambodia", "Bangladesh", "Lao PDR", "Nepal", "Indonesia", "Thailand",
  "Overview", "Historical arc", "Counterfactual", "Synthetic", "Illustrative", "No coup",
  "Actual continuation", "Partial recovery", "Reform push", "Combined", "GDP per capita", "History",
];

/** Checks every view shares in Burmese: language, digits, no English names, nothing clipped. */
const BURMESE_COMMON = `[
  ["the page language is Burmese", document.documentElement.lang === "my", document.documentElement.lang],
  ["the Noto Sans Myanmar face has loaded", [...document.fonts].some((f) => f.family.includes("Noto Sans Myanmar") && f.status === "loaded"), ""],
  ["numerals stay Western (no Myanmar digits)", !/[\u1040-\u1049]/u.test(document.body.innerText), ""],
  ["no English name in the nav, legends, labels or titles", (() => {
    const text = [...document.querySelectorAll(".nav, .legend, .end-labels, .chart-frame__title, .recharts-label, .scenario__label, select, .layer__eyebrow, .window-bracket")]
      .map((el) => el.textContent).join(" | ");
    return !${JSON.stringify(ENGLISH_NAMES)}.some((name) => text.includes(name));
  })(), ${JSON.stringify(ENGLISH_NAMES)}.filter((name) => [...document.querySelectorAll(".nav, .legend, .end-labels, .chart-frame__title, .recharts-label, .scenario__label, select, .layer__eyebrow, .window-bracket")].some((el) => el.textContent.includes(name))).join(", ")],
  ["no clipped text in nav, buttons, pills, banners, titles or legends", (() => clipped().length === 0)(), clipped().slice(0, 4).join("; ")],
]`;

/**
 * The link-preview card, laid over the loaded overview: its brand and headline,
 * then a copy of the GDP chart's frame without its foot, scaled to fit 630 px.
 * Returns [chart height, room] for the log.
 */
const OG_CARD = `(() => {
  const card = document.createElement("div");
  card.style.cssText = "position:fixed;inset:0;z-index:100;display:flex;flex-direction:column;gap:20px;" +
    "padding:36px 48px;background:var(--bg);overflow:hidden";
  const head = document.createElement("div");
  head.style.cssText = "display:flex;align-items:baseline;justify-content:space-between;gap:24px";
  const brand = document.querySelector(".brand").cloneNode(true);
  brand.style.fontSize = "var(--text-lg)";
  const headline = document.createElement("p");
  headline.textContent = document.querySelector("main h1").textContent;
  headline.style.cssText = "margin:0;color:var(--text-2);font-size:var(--text-lg);font-weight:var(--weight-semibold)";
  head.append(brand, headline);
  const chart = document.querySelector("main figure.chart-frame").cloneNode(true);
  chart.querySelector(".chart-frame__foot")?.remove();
  chart.querySelector(".legend--narrow-only")?.remove();
  card.append(head, chart);
  document.body.append(card);
  document.documentElement.style.overflow = "hidden"; // no scrollbar in the picture
  window.scrollTo(0, 0);
  const room = window.innerHeight - 72 - head.offsetHeight - 20;
  if (chart.offsetHeight > room) chart.style.zoom = String(room / chart.offsetHeight);
  return [chart.offsetHeight, room];
})()`;

/** Under reduced motion every animated number must already show its final value. */
const NUMBERS_FINAL = `[...document.querySelectorAll("[data-animated-number]")].every((el) =>
  el.textContent === el.nextElementSibling?.textContent)`;

const HELPERS = `
  const visible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return el.checkVisibility() && r.width > 0 && r.height > 0 && r.left >= -1 && r.right <= window.innerWidth + 1;
  };
  // A chart whose marks span under half its width has collapsed (a degenerate scale).
  const collapsedCharts = () => [...document.querySelectorAll("figure svg.recharts-surface")].flatMap((svg) => {
    const width = svg.getBoundingClientRect().width;
    const marks = [...svg.querySelectorAll(".recharts-line-curve, .recharts-bar-rectangle path, .recharts-bar-rectangle rect")];
    if (marks.length === 0 || width === 0) return [];
    const boxes = marks.map((m) => m.getBoundingClientRect()).filter((b) => b.width > 0 || b.height > 0);
    const span = boxes.length ? Math.max(...boxes.map((b) => b.right)) - Math.min(...boxes.map((b) => b.left)) : 0;
    const isBar = svg.querySelector(".recharts-bar-rectangle") !== null;
    const min = isBar ? width * 0.15 : width * 0.5;
    return span >= min ? [] : [(svg.closest("figure")?.querySelector("h3")?.textContent ?? "chart") + ": marks span " + Math.round(span) + "px of " + Math.round(width)];
  });
  // Text boxes that are cut off: content taller or wider than the box that shows it.
  const clipped = () => [...document.querySelectorAll(
    ".nav__link, .nav__list, .button, .pill, .banner__title, .chart-frame__title, .legend__item, " +
    ".language-toggle__option, .stat__label, .stat__value, .eyebrow, .layer__eyebrow, .layer__title, .layer__cta, " +
    ".scenario__label, .section-header__title, .sources__group-title, .about__learn a, .about__draft")]
    .filter((el) => el.checkVisibility() && !el.matches(".nav__list") && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)
      || el.matches(".nav__list") && el.scrollHeight > el.clientHeight + 1
      // ...or that run off the right edge (the nav and the data tables scroll sideways by design).
      || el.checkVisibility() && el.getBoundingClientRect().right > window.innerWidth + 1 && !el.closest(".nav__list, .data-table__scroll"))
    .map((el) => el.className.split(" ")[0] + ": " + el.textContent.slice(0, 24));
  const textEl = (text) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement;
      if (node.textContent.includes(text) && !el.closest(".sr-only, details:not([open])")) return el;
    }
    return null;
  };
`;

async function main() {
  const browser = await launch();
  const cdp = connect(browser.wsUrl);
  await cdp.ready;
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");
  await cdp.send("DOM.enable");
  await cdp.send("CSS.enable");

  const requests = [];
  const errors = [];
  cdp.on((message) => {
    if (message.method === "Network.requestWillBeSent") requests.push(message.params.request);
    if (message.method === "Runtime.exceptionThrown") {
      errors.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
    }
  });

  const evaluate = async (expression) => {
    const { result, exceptionDetails } = await cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? exceptionDetails.text);
    return result.value;
  };

  /** Wait until the view has loaded: charts drawn, no loading or waking state left. */
  const settle = async (view) => {
    const deadline = Date.now() + VIEW_TIMEOUT;
    while (Date.now() < deadline) {
      // Banners say what they are in data-banner, so this reads the same in any language.
      const state = await evaluate(`(() => ({
        loading: document.querySelectorAll("[data-loading], [data-status]:not([hidden])").length,
        waking: document.querySelectorAll("[data-banner=waking]").length > 0,
        failed: [...document.querySelectorAll("[data-banner=error]")].map((el) => el.textContent),
        charts: document.querySelectorAll("figure .recharts-surface").length,
      }))()`);
      if (state.failed.length > 0) throw new Error(`${view}: error shown: ${state.failed.join(" | ")}`);
      // About draws no chart; it is ready once nothing is loading.
      if (state.loading === 0 && (state.charts > 0 || view === "about")) {
        await sleep(400); // let Recharts finish its resize pass
        return;
      }
      await sleep(250);
    }
    throw new Error(`${view}: did not finish loading within ${VIEW_TIMEOUT / 1000} s`);
  };

  /**
   * A viewport shot, or a full-page one. Full-page shots grow the emulated
   * viewport to the page's height and let the charts re-measure first:
   * capturing beyond the viewport catches responsive charts mid-resize.
   */
  const screenshot = async (name, viewport, fullPage = false) => {
    // Let the first-view reveal (line draws, band, count-ups) finish: about 2 s at most.
    await sleep(ANIMATION_SETTLE_MS);
    if (!SHOTS) return;
    mkdirSync(SHOTS, { recursive: true });
    if (fullPage) {
      const { cssContentSize } = await cdp.send("Page.getLayoutMetrics");
      await cdp.send("Emulation.setDeviceMetricsOverride", { ...viewport, height: Math.ceil(cssContentSize.height) });
      await sleep(800);
    }
    const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
    if (fullPage) {
      await cdp.send("Emulation.setDeviceMetricsOverride", viewport);
      await sleep(400);
    }
    writeFileSync(join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
    console.log(`  saved ${join(SHOTS, `${name}.png`)}`);
  };

  /** Move an input[type=range] the way a user would, so React sees the change. */
  const moveSlider = (selector, value) =>
    evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, ${JSON.stringify(String(value))});
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    })()`);

  const pathOf = (index = 0) =>
    evaluate(`[...document.querySelectorAll("figure .recharts-line-curve, figure .recharts-curve.recharts-line-curve")]
      .map((p) => p.getAttribute("d")).join("|").slice(0, 4000) + ":" + ${index}`);

  /** The fonts the browser actually painted a node's text with - so tofu or a wrong fallback shows. */
  const paintedFonts = async (selector) => {
    const { root } = await cdp.send("DOM.getDocument", { depth: -1 });
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector });
    if (!nodeId) return [];
    const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
    return fonts.map((f) => `${f.familyName} (${f.glyphCount})`);
  };

  const results = [];
  const record = (viewport, view, label, passed, detail = "") => {
    results.push({ viewport, view, label, passed, detail });
    console.log(`  ${passed ? "ok  " : "FAIL"} ${label}${detail ? ` (${detail})` : ""}`);
  };

  // Downloads land in a folder of our own, so the exports can be read back.
  const downloads = EXPORTS ?? mkdtempSync(join(tmpdir(), "amber-exports-"));
  mkdirSync(downloads, { recursive: true });
  await cdp.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloads }).catch(() =>
    // Older builds take it only on the page.
    cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: downloads }),
  );

  /** Click a chart's download button and wait for the file; returns its bytes, or null. */
  const exportFrom = async (figureIndex, label, file) => {
    const path = join(downloads, file);
    rmSync(path, { force: true });
    const clicked = await evaluate(`(() => {
      const figure = document.querySelectorAll("figure.chart-frame")[${figureIndex}];
      const button = figure?.querySelector(${JSON.stringify(`button[aria-label="${label}"]`)});
      button?.click();
      return Boolean(button);
    })()`);
    if (!clicked) return null;
    for (let i = 0; i < 80 && !existsSync(path); i++) await sleep(250);
    await sleep(300); // the file is written, then renamed into place
    return existsSync(path) ? readFileSync(path) : null;
  };
  const pngSize = (bytes) => (bytes && bytes.subarray(1, 4).toString() === "PNG" ? [bytes.readUInt32BE(16), bytes.readUInt32BE(20)] : null);

  try {
    // The share card, in the page as served: crawlers read it without running the app.
    const html = await (await fetch(`${APP_URL}/`)).text();
    const tag = (key) => new RegExp(`<meta\\s+(?:property|name)="${key}"\\s+content="([^"]*)"`).exec(html)?.[1] ?? null;
    record("http", "card", "the page carries Open Graph and Twitter card tags",
      ["og:title", "og:description", "og:image", "twitter:card", "twitter:image"].every((key) => tag(key)), "");
    record("http", "card", "its image URL is absolute", /^https:\/\//.test(tag("og:image") ?? ""), tag("og:image") ?? "");
    const image = await fetch(`${APP_URL}/og-image.png`);
    const imageSize = pngSize(Buffer.from(await image.arrayBuffer()));
    record("http", "card", "the card image is served, 1200 x 630", image.ok && imageSize?.join("x") === "1200x630",
      `${image.status} ${imageSize?.join("x") ?? "not a PNG"}`);

    for (const viewport of VIEWPORTS) {
      await cdp.send("Emulation.setDeviceMetricsOverride", viewport);
      await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: viewport.mobile });
      for (const view of Object.keys(VIEW_CHECKS)) {
        console.log(`${viewport.name} ${view}`);
        // A fresh load per view, so every check also covers the loading -> loaded
        // transition. About is reached through a URL that names no view.
        const loaded = cdp.once("Page.loadEventFired");
        await cdp.send("Page.navigate", { url: viewUrl(`${viewport.name}-${view}`, view === "about" ? "" : view) });
        await loaded;
        try {
          await settle(view);
        } catch (error) {
          record(viewport.name, view, "view loads", false, error.message);
          continue;
        }
        record(viewport.name, view, "view loads", true);
        const overflow = await evaluate("document.documentElement.scrollWidth - window.innerWidth");
        record(viewport.name, view, "no horizontal page overflow", overflow <= 1, `${overflow}px`);
        const narrowCharts = await evaluate(`(() => { ${HELPERS} return collapsedCharts(); })()`);
        record(viewport.name, view, "every chart draws across its plot", narrowCharts.length === 0, narrowCharts.join("; "));
        const checks = await evaluate(`(() => { ${HELPERS} return ${VIEW_CHECKS[view]}; })()`);
        for (const [label, passed, detail] of checks) record(viewport.name, view, label, passed, detail);
        if (view === "overview") {
          // Even on an English page the toggle names Burmese in Burmese: it must not be tofu.
          const fonts = await paintedFonts(".language-toggle__option[lang=my]");
          record(viewport.name, view, "the toggle's Burmese name is painted in Noto Sans Myanmar",
            fonts.some((f) => f.includes("Noto Sans Myanmar")), fonts.join(", "));
        }
        if (SHOTS && ALL_SHOTS) await screenshot(`qa-${viewport.name}-${view}`, viewport, true);
        if (SHOTS && viewport.name === "desktop" && (view === "about" || view === "overview" || view === "future")) {
          await screenshot(`app-${view}`, viewport);
        }


        if (SHOTS && viewport.name === "desktop" && view === "history") {
          await screenshot("app-history", viewport);
          await evaluate(`(() => { [...document.querySelectorAll("figure")].at(-1)?.scrollIntoView(); window.scrollBy(0, -72); })()`);
          await sleep(300);
          await screenshot("app-history-divergence", viewport);
        }
        if (SHOTS && viewport.name === "mobile" && view === "counterfactual") {
          await evaluate(`document.querySelectorAll(".outcome")[1]?.scrollIntoView()`);
          await sleep(300);
          await screenshot("app-mobile", viewport);
        }

        // The player: pressing play advances the year, and the caveat stays on screen
        // through every step (it changes with the data, never after it).
        if (view === "future" || view === "history") {
          const readYear = () => evaluate(`document.querySelector(".scrubber__year")?.textContent ?? ""`);
          const before = await readYear();
          await evaluate(`document.querySelector(".scrubber__play")?.click()`);
          await sleep(1600);
          const during = await readYear();
          const caveat = await evaluate(`(() => { ${HELPERS} return ${JSON.stringify(view)} === "future"
            ? [...document.querySelectorAll(".player [data-caveat]")].some((el) => visible(el))
            : [...document.querySelectorAll("[role=note]")].some((el) => el.textContent.includes("not a causal estimate") && visible(el)); })()`);
          await evaluate(`document.querySelector(".scrubber__play")?.click()`);
          record(viewport.name, view, "pressing play steps through the years", during !== before && during !== "", `${before} -> ${during}`);
          record(viewport.name, view, "the caveat stays visible while it plays", caveat);
        }

        // Live controls: a change must call the API and redraw the chart.
        if (view === "past" || view === "future") {
          const endpoint = view === "past" ? "/index" : "/simulate";
          const before = await pathOf();
          const seen = requests.length;
          await moveSlider(".slider input[type=range]", view === "past" ? "0.2" : "1.5");
          const deadline = Date.now() + 30_000;
          let called = false;
          let redrawn = false;
          while (Date.now() < deadline && !(called && redrawn)) {
            await sleep(250);
            called = requests.slice(seen).some((r) => new URL(r.url).pathname === endpoint);
            redrawn = called && (await pathOf()) !== before;
          }
          record(viewport.name, view, `moving a control calls ${endpoint}`, called);
          record(viewport.name, view, "and the chart redraws", redrawn);
          const search = await evaluate("location.search");
          record(viewport.name, view, "and the URL records it", search.includes(view === "past" ? "weights=" : "levers="), search);
        }

        // Downloads: the CSV holds the loaded series with the coverage caveat; the
        // PNG is the chart itself. Then the footer's sources link lands on the list.
        if (view === "past" && viewport.name === "desktop") {
          await sleep(ANIMATION_SETTLE_MS); // export the redrawn chart, not the tween
          const csv = (await exportFrom(1, "Download this chart's data as CSV", "amber-development-index.csv"))?.toString("utf8") ?? "";
          record(viewport.name, view, "the CSV download arrives with the coverage caveat first",
            csv.includes("# Hollow points are computed from fewer than all index indicators"), `${csv.length} bytes`);
          record(viewport.name, view, "and holds the loaded series and their coverage",
            /\r\nYear,.*Myanmar: indicator coverage/.test(csv) && /\r\n2011,[\d.]+,/.test(csv), "");
          const png = pngSize(await exportFrom(1, "Download this chart as a PNG image", "amber-development-index.png"));
          record(viewport.name, view, "the PNG download arrives, at twice the chart's size", png != null && png[0] >= 2000, png?.join("x") ?? "none");
          await evaluate(`document.querySelector(".shell-footer a[href$='#sources']").click()`);
          await sleep(1500);
          const landed = await evaluate(`(() => { const r = document.getElementById("sources")?.getBoundingClientRect();
            return [location.search + location.hash, r ? Math.round(r.top) : -1]; })()`);
          record(viewport.name, view, "the footer's sources link opens the list", landed[0] === "#sources" && landed[1] >= 0 && landed[1] < 200,
            landed.join(" at "));
        }

        // A shared link rebuilds the view it names: scenario, levers and series.
        if (view === "future" && viewport.name === "desktop") {
          const loadedLink = cdp.once("Page.loadEventFired");
          await cdp.send("Page.navigate", {
            url: viewUrl("link", "future", "&scenario=reform_push&levers=fdi_openness:1.25&series=NY.GDP.PCAP.KD"),
          });
          await loadedLink;
          await settle("future link");
          const state = await evaluate(`[
            document.querySelector("input[name=scenario]:checked")?.value,
            document.querySelector(".slider input[type=range]")?.value,
            document.querySelector(".select select")?.value,
            history.length,
          ]`);
          record(viewport.name, view, "a shared link rebuilds its scenario, lever and series",
            state[0] === "reform_push" && state[1] === "1.25" && state[2] === "NY.GDP.PCAP.KD", state.slice(0, 3).join(", "));
          await moveSlider(".slider input[type=range]", "0.9");
          await sleep(800);
          const after = await evaluate("[location.search, history.length]");
          record(viewport.name, view, "a control change rewrites the URL in place, with no new history entry",
            after[0].includes("levers=fdi_openness:0.9") && after[1] === state[3], after.join(", "));
        }
      }
    }
    // Reduced motion: the final state renders at once - no count-up, no draw.
    await cdp.send("Emulation.setDeviceMetricsOverride", VIEWPORTS[0]);
    await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
    for (const view of ["overview", "future", "history"]) {
      const loaded = cdp.once("Page.loadEventFired");
      await cdp.send("Page.navigate", { url: viewUrl(`reduced-${view}`, view) });
      await loaded;
      await settle(view);
      const final = await evaluate(NUMBERS_FINAL);
      const count = await evaluate(`document.querySelectorAll("[data-animated-number]").length`);
      record("reduced-motion", view, "every animated number already shows its final value", final, `${count} numbers`);
    }
    await cdp.send("Emulation.setEmulatedMedia", { features: [] });

    // Burmese: chosen by the browser's language, as a reader in Myanmar would arrive.
    const { userAgent } = await cdp.send("Browser.getVersion");
    await cdp.send("Network.setUserAgentOverride", { userAgent, acceptLanguage: "my-MM,my;q=0.9" });
    for (const viewport of VIEWPORTS) {
      await cdp.send("Emulation.setDeviceMetricsOverride", viewport);
      await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: viewport.mobile });
      for (const view of Object.keys(BURMESE_CHECKS)) {
        const where = `my-${viewport.name}`;
        console.log(`${where} ${view}`);
        const loaded = cdp.once("Page.loadEventFired");
        await cdp.send("Page.navigate", { url: viewUrl(`${where}-${view}`, view === "about" ? "" : view) });
        await loaded;
        try {
          await settle(view);
        } catch (error) {
          record(where, view, "view loads", false, error.message);
          continue;
        }
        record(where, view, "view loads", true);
        await sleep(600); // the Burmese face swaps in once it has downloaded
        const overflow = await evaluate("document.documentElement.scrollWidth - window.innerWidth");
        record(where, view, "no horizontal page overflow", overflow <= 1, `${overflow}px`);
        const checks = await evaluate(`(() => { ${HELPERS} return [...${BURMESE_COMMON}, ...${BURMESE_CHECKS[view]}]; })()`);
        for (const [label, passed, detail] of checks) record(where, view, label, passed, detail);
        const fonts = await paintedFonts("main h1");
        record(where, view, "the view title is painted in Noto Sans Myanmar", fonts.some((f) => f.includes("Noto Sans Myanmar")), fonts.join(", "));
        if (SHOTS && ALL_SHOTS) await screenshot(`qa-${where}-${view}`, viewport, true);
        if (SHOTS && viewport.name === "desktop" && view === "overview") await screenshot("app-my-overview", viewport);
        if (SHOTS && ALL_SHOTS && viewport.name === "desktop" && view === "about") await screenshot("qa-my-about", viewport);

        // A Burmese chart exported as PNG: drawn with the embedded Burmese face (keep it with --exports).
        if (viewport.name === "desktop" && view === "counterfactual") {
          await sleep(ANIMATION_SETTLE_MS); // export the drawn chart, not the reveal
          const png = pngSize(await exportFrom(0, my("export.pngLabel"), "amber-counterfactual-ny-gdp-pcap-kd.png"));
          record(where, view, "a Burmese chart exports as PNG", png != null && png[0] >= 2000, png?.join("x") ?? "none");
        }
        if (SHOTS && viewport.name === "mobile" && view === "counterfactual") {
          await evaluate(`document.querySelectorAll(".outcome")[1]?.scrollIntoView()`);
          await sleep(300);
          await screenshot("app-my-mobile", viewport);
        }

        // The toggle: back to English and to Burmese again, on the same page.
        if (viewport.name === "desktop" && view === "overview") {
          const read = `[document.documentElement.lang, document.querySelector(".nav__link[href*='view=overview']").textContent, location.search]`;
          await evaluate(`document.querySelector(".language-toggle__option[lang=en]").click()`);
          await sleep(300);
          const english = await evaluate(read);
          await evaluate(`document.querySelector(".language-toggle__option[lang=my]").click()`);
          await sleep(300);
          const burmese = await evaluate(read);
          record(where, view, "the toggle switches to English", english[0] === "en" && english[1] === "Overview", english.join(" / "));
          record(where, view, "and back to Burmese", burmese[0] === "my" && burmese[1] === my("nav.overview"), burmese.join(" / "));
          // A Burmese browser that chose English keeps it on reload: the URL names it.
          record(where, view, "the URL names the chosen language", english[2].includes("lang=en") && burmese[2].includes("lang=my"),
            `${english[2]} / ${burmese[2]}`);
        }
      }
    }
    await cdp.send("Network.setUserAgentOverride", { userAgent, acceptLanguage: "en-US,en;q=0.9" });

    // --gif <dir>: frames of the Future player playing a scenario forward, for the
    // README's animated asset (assemble them with any GIF tool; see CHANGELOG).
    if (args.gif) {
      const dir = resolve(args.gif);
      mkdirSync(dir, { recursive: true });
      const tall = { ...VIEWPORTS[0], height: 1500 };
      await cdp.send("Emulation.setDeviceMetricsOverride", tall);
      const loaded = cdp.once("Page.loadEventFired");
      await cdp.send("Page.navigate", { url: viewUrl("gif", "future") });
      await loaded;
      await settle("future");
      await sleep(ANIMATION_SETTLE_MS);
      const clip = await evaluate(`(() => {
        const chart = document.querySelector(".split__main figure").getBoundingClientRect();
        const player = document.querySelector(".player").getBoundingClientRect();
        const top = chart.top + window.scrollY - 8;
        return { x: chart.left - 8, y: top, width: chart.width + 16, height: player.bottom + window.scrollY - top + 8, scale: 1 };
      })()`);
      // One frame per year, once that year's numbers and bars have settled (the
      // 240 ms step tween), so no frame shows a value between two years.
      const readYear = () => evaluate(`document.querySelector(".scrubber__year").textContent`);
      await evaluate(`document.querySelector(".scrubber__play").click()`);
      const deadline = Date.now() + 30_000;
      let frame = 0;
      let last = "";
      while (Date.now() < deadline) {
        const year = await readYear();
        if (year !== last) {
          last = year;
          await sleep(300);
          const { data } = await cdp.send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
          writeFileSync(join(dir, `frame-${String(frame++).padStart(3, "0")}-${year}.png`), Buffer.from(data, "base64"));
        }
        const playing = await evaluate(`document.querySelector(".scrubber__play").getAttribute("aria-pressed") === "true"`);
        if (!playing && frame > 3) break;
        await sleep(40);
      }
      console.log(`  saved ${frame} GIF frames to ${dir}`);
    }

    // --og <file>: the 1200 x 630 link-preview image - the brand, the overview's
    // headline and its GDP chart, subtitle (the estimate's caveat) included -
    // composed from the live page in the light theme, motion off.
    if (args.og) {
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
      await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: false });
      await cdp.send("Emulation.setEmulatedMedia", {
        features: [
          { name: "prefers-color-scheme", value: "light" },
          { name: "prefers-reduced-motion", value: "reduce" },
        ],
      });
      const loaded = cdp.once("Page.loadEventFired");
      await cdp.send("Page.navigate", { url: viewUrl("og", "overview") });
      await loaded;
      await settle("overview");
      await sleep(800);
      const fit = await evaluate(OG_CARD);
      await sleep(400);
      const { data } = await cdp.send("Page.captureScreenshot", {
        format: "png",
        clip: { x: 0, y: 0, width: 1200, height: 630, scale: 1 },
      });
      writeFileSync(resolve(args.og), Buffer.from(data, "base64"));
      console.log(`  saved ${resolve(args.og)} (chart ${fit.join(" px in ")} px)`);
      await cdp.send("Emulation.setEmulatedMedia", { features: [] });
    }
  } finally {
    cdp.close();
    browser.close();
    if (!EXPORTS) rmSync(downloads, { recursive: true, force: true });
  }

  record("all", "all", "no uncaught page errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  const failed = results.filter((r) => !r.passed);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed against ${APP_URL}`);
  process.exit(failed.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

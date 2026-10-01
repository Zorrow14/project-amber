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
 *   npm run build && npx vite preview --port 4173 &   # plus the API on :8000
 *   node scripts/smoke.mjs --url http://localhost:4173
 *   node scripts/smoke.mjs --url https://<your-app>.vercel.app --screenshots ../docs/images
 *
 * Options: --url (default http://localhost:4173), --browser <path> (or $BROWSER),
 * --screenshots <dir> (writes the README images: app-overview, app-future, app-mobile),
 * --all (with --screenshots: also a full-page shot of every view at both widths, for QA),
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
const APP_URL = (args.url ?? "http://localhost:4173").replace(/\/+$/, "");
const VIEW_TIMEOUT = Number(args.timeout ?? 120_000);
const SHOTS = args.screenshots ? resolve(args.screenshots) : null;
const ALL_SHOTS = args.all === "true";

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

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900, deviceScaleFactor: 1, mobile: false },
  { name: "mobile", width: 375, height: 812, deviceScaleFactor: 2, mobile: true },
];

/** In-page assertions per view. Each returns [label, passed, detail]. */
const VIEW_CHECKS = {
  overview: `[
    ["framing: 'analytical instrument' is shown", visible(textEl("analytical instrument")), ""],
    ["the GDP divergence chart rendered", document.querySelectorAll("figure .recharts-line").length >= 7, ""],
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
  ]`,
};

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
      const state = await evaluate(`(() => ({
        loading: document.querySelectorAll("[data-loading], [data-status]:not([hidden])").length,
        waking: document.body.textContent.includes("Waking the server"),
        failed: [...document.querySelectorAll("[role=alert]")].map((el) => el.textContent)
          .filter((t) => !t.includes("Not a credible") && !t.includes("Illustrative dynamics, not")),
        charts: document.querySelectorAll("figure .recharts-surface").length,
      }))()`);
      if (state.failed.length > 0) throw new Error(`${view}: error shown: ${state.failed.join(" | ")}`);
      if (state.loading === 0 && state.charts > 0) {
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

  const results = [];
  const record = (viewport, view, label, passed, detail = "") => {
    results.push({ viewport, view, label, passed, detail });
    console.log(`  ${passed ? "ok  " : "FAIL"} ${label}${detail ? ` (${detail})` : ""}`);
  };

  try {
    for (const viewport of VIEWPORTS) {
      await cdp.send("Emulation.setDeviceMetricsOverride", viewport);
      await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: viewport.mobile });
      for (const view of Object.keys(VIEW_CHECKS)) {
        console.log(`${viewport.name} #/${view}`);
        // A fresh load per view (a distinct query string defeats same-document hash
        // navigation), so every check also covers the loading -> loaded transition.
        const loaded = cdp.once("Page.loadEventFired");
        await cdp.send("Page.navigate", { url: `${APP_URL}/?smoke=${viewport.name}-${view}#/${view}` });
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
        if (SHOTS && ALL_SHOTS) await screenshot(`qa-${viewport.name}-${view}`, viewport, true);
        if (SHOTS && viewport.name === "desktop" && (view === "overview" || view === "future")) {
          await screenshot(`app-${view}`, viewport);
        }
        if (SHOTS && viewport.name === "mobile" && view === "counterfactual") {
          await evaluate(`document.querySelectorAll(".outcome")[1]?.scrollIntoView()`);
          await sleep(300);
          await screenshot("app-mobile", viewport);
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
        }
      }
    }
  } finally {
    cdp.close();
    browser.close();
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

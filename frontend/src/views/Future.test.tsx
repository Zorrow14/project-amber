import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import type { Meta, ScenarioResult, ScenariosResponse, SDCredibility, SimulateResponse } from "../api/types";
import { MetaProvider } from "../context/meta";
import { MetaContext } from "../context/metaContext";
import { RouteProvider } from "../context/route";
import { InBurmese } from "../test/i18n";
import { twin } from "../test/twin";
import { Future } from "./Future";

// The honesty guard for the Future view: a model that failed its backtest gate
// must say so - banner, "Illustrative dynamics" badge, "Scenarios, not
// forecasts" - and keep saying so while a lever change is being re-run.

const NOT_CREDIBLE = "The model misses history by more than the gate allows: read these as illustrative dynamics.";
const FRAMING = "These are scenarios under stated assumptions, not forecasts.";

const years = [2024, 2025, 2026];
const bands = { p10: [0.5, 0.52, 0.53], p50: [0.52, 0.55, 0.57], p90: [0.54, 0.58, 0.6] };

const credibility: SDCredibility = {
  credible: false,
  overall_nrmse: 0.2,
  threshold: 0.1,
  message: NOT_CREDIBLE,
  message_i18n: twin(NOT_CREDIBLE),
  framing: FRAMING,
  framing_i18n: twin(FRAMING),
  composition_gap: 0.027,
  last_observed_year: 2024,
  unidentified: ["connectivity_tfp", "savings_rate"],
  unidentified_labels: ["the connectivity effect", "the savings rate"],
  unidentified_labels_i18n: [twin("the connectivity effect"), twin("the savings rate")],
  profile_flat: true,
  metrics: [],
};

function result(name: string, label: string): ScenarioResult {
  return {
    name,
    label,
    label_i18n: twin(label),
    description: `${label} description`,
    description_i18n: twin(`${label} description`),
    custom: false,
    levers: { education_spend: 1 },
    stability: [],
    diverges_from: 2024,
    series: { combined: bands },
    gaps: null,
    sc_checks: [],
  };
}

const scenarios: ScenariosResponse = {
  years,
  projection_start: 2025,
  quantiles: ["p10", "p50", "p90"],
  credibility,
  history: { years: [2024], gdp_pc: [1158], combined: [0.52], combined_coverage: [0.67] },
  sc_overlay: [],
  scenarios: [result("actual_continuation", "Actual continuation"), result("no_coup", "No coup")],
};

const simulated: SimulateResponse = {
  years,
  projection_start: 2025,
  quantiles: ["p10", "p50", "p90"],
  baseline: "actual_continuation",
  credibility,
  result: result("no_coup", "No coup"),
};

const meta = {
  treatment_year: 2021,
  modeling_window: { start: 2011, end: 2024 },
  horizon_end: 2026,
  projection_start: 2025,
  covid_years: [2020],
  ensemble_size: 200,
  baseline_scenario: "actual_continuation",
  counterfactual_scenario: "no_coup",
  countries: [{ iso3: "MMR", name: "Myanmar", treated: true, donor: false }],
  sc_outcomes: [],
  pillars: [],
  sd_series: [{ id: "combined", label: "Combined development index", kind: "combined" }],
  scenarios: [
    { name: "actual_continuation", label: "Actual continuation", description: "", levers: { education_spend: 1 } },
    { name: "no_coup", label: "No coup", description: "", levers: { education_spend: 1 } },
  ],
  levers: [
    { name: "education_spend", label: "Education spending", min: 0.5, max: 2, step: 0.05, default: 1, description: "" },
  ],
  framing: { scenario: FRAMING },
} as unknown as Meta;

// Burmese twins, as the API sends them beside every display string.
const BURMESE: Record<string, string> = {
  "Actual continuation": "လက်ရှိအတိုင်း ဆက်လက်",
  "No coup": "အာဏာသိမ်းမှု မရှိ",
};
const NOT_CREDIBLE_MY = "မော်ဒယ်သည် သမိုင်းကို ခွင့်ပြုထားသည်ထက် ပိုလွဲသည်: သရုပ်ပြ ရွေ့လျားပုံအဖြစ်သာ ဖတ်ပါ။";
const FRAMING_MY =
  "ဖြစ်နိုင်ခြေ အခြေအနေများ၊ ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ: ဖော်ပြထားသော ယူဆချက်များအောက်ရှိ ဖြစ်နိုင်ခြေ အခြေအနေများ။";

const burmeseMeta = {
  ...meta,
  countries: [{ iso3: "MMR", name: "Myanmar", name_i18n: twin("Myanmar", "မြန်မာ"), treated: true, donor: false }],
  sd_series: [
    {
      id: "combined",
      label: "Combined development index",
      label_i18n: twin("Combined development index", "ပေါင်းစပ် ဖွံ့ဖြိုးမှု ညွှန်းကိန်း"),
      kind: "combined",
    },
  ],
  scenarios: meta.scenarios.map((s) => ({
    ...s,
    label_i18n: twin(s.label, BURMESE[s.label]),
    description_i18n: twin("", ""),
  })),
  levers: meta.levers.map((l) => ({
    ...l,
    label_i18n: twin(l.label, "ပညာရေး အသုံးစရိတ်"),
    description_i18n: twin("", ""),
  })),
  framing_i18n: { scenario: twin(FRAMING, FRAMING_MY) },
} as unknown as Meta;

function inBurmese(r: ScenarioResult): ScenarioResult {
  const label = BURMESE[r.label] ?? r.label;
  return { ...r, label_i18n: twin(r.label, label), description_i18n: twin(r.description, `${label} ဖော်ပြချက်`) };
}

const simulate = vi.fn();
const precomputed = vi.fn(() => Promise.resolve(scenarios));
const metaCall = vi.fn(() => Promise.resolve(burmeseMeta));
vi.mock("../api/client", async (original) => ({
  ...(await original<typeof import("../api/client")>()),
  api: {
    meta: () => metaCall(),
    scenarios: () => precomputed(),
    simulate: (...args: unknown[]) => simulate(...args),
  },
}));

async function findChart(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { name: /No coup, to 2026/ });
  const figure = heading.closest("figure");
  if (!figure) throw new Error("The chart heading is not inside its figure");
  return figure;
}

function renderFuture() {
  return render(
    <MetaContext.Provider value={meta}>
      <Future />
    </MetaContext.Provider>,
  );
}

function renderFromUrl() {
  return render(
    <RouteProvider>
      <MetaContext.Provider value={meta}>
        <Future />
      </MetaContext.Provider>
    </RouteProvider>,
  );
}

afterEach(() => window.history.replaceState(null, "", "/"));

describe("Future", () => {
  it("reproduces a shared link, and records lever changes in place", async () => {
    simulate.mockResolvedValue(simulated);
    window.history.replaceState(null, "", "/?view=future&scenario=actual_continuation&levers=education_spend:1.25");
    const entries = window.history.length;
    const first = renderFromUrl();

    // The URL's scenario and lever reach the controls and the run.
    expect(screen.getByRole("radio", { name: /Actual continuation/ })).toBeChecked();
    expect(screen.getByLabelText("Education spending")).toHaveValue("1.25");
    await waitFor(() =>
      expect(simulate).toHaveBeenLastCalledWith({ scenario: "actual_continuation", levers: { education_spend: 1.25 } }, expect.anything()),
    );

    // A lever change rewrites the URL without adding a history entry.
    fireEvent.change(screen.getByLabelText("Education spending"), { target: { value: "1.5" } });
    await waitFor(() =>
      expect(window.location.search).toBe("?view=future&scenario=actual_continuation&levers=education_spend:1.5"),
    );
    expect(window.history.length).toBe(entries);

    // Reloading that URL rebuilds the same view.
    first.unmount();
    renderFromUrl();
    expect(screen.getByRole("radio", { name: /Actual continuation/ })).toBeChecked();
    expect(screen.getByLabelText("Education spending")).toHaveValue("1.5");

    // Back at the preset, the parameter goes: the URL holds only what differs from the defaults.
    fireEvent.change(screen.getByLabelText("Education spending"), { target: { value: "1" } });
    await waitFor(() => expect(window.location.search).toBe("?view=future&scenario=actual_continuation"));
  });

  it("ignores what a hand-edited link gets wrong", () => {
    simulate.mockResolvedValue(simulated);
    window.history.replaceState(null, "", "/?view=future&scenario=nonsense&levers=education_spend:9,bogus:1");
    renderFromUrl();
    expect(screen.getByRole("radio", { name: /No coup/ })).toBeChecked(); // the default scenario
    expect(screen.getByLabelText("Education spending")).toHaveValue("2"); // clamped to the lever's range
  });

  it("keeps every caveat visible through a lever change for a non-credible model", async () => {
    simulate.mockResolvedValueOnce(simulated);
    renderFuture();

    const chart = await findChart();
    expect(screen.getByText("Scenarios, not forecasts")).toBeVisible();
    expect(within(screen.getByRole("alert")).getByText(NOT_CREDIBLE)).toBeVisible();
    expect(within(chart).getByText("Illustrative dynamics")).toBeVisible();

    // A lever change starts a new run that has not answered yet.
    simulate.mockReturnValue(new Promise(() => {}));
    fireEvent.change(screen.getByLabelText("Education spending"), { target: { value: "1.5" } });
    await waitFor(() => expect(within(chart).getByText("Updating…")).toBeVisible());

    // The status sits beside the caveat, never in its place.
    expect(within(chart).getByText("Illustrative dynamics")).toBeVisible();
    expect(screen.getByText("Scenarios, not forecasts")).toBeVisible();
    expect(within(screen.getByRole("alert")).getByText(NOT_CREDIBLE)).toBeVisible();
    expect(within(chart).getByText(/Illustrative dynamics only/)).toBeInTheDocument(); // the text alternative
  });

  it("names scenarios, levers and series in Burmese from /meta, and keeps every caveat", async () => {
    const burmeseCredibility = { ...credibility, message_i18n: twin(NOT_CREDIBLE, NOT_CREDIBLE_MY) };
    precomputed.mockResolvedValueOnce({
      ...scenarios,
      credibility: burmeseCredibility,
      scenarios: scenarios.scenarios.map(inBurmese),
    });
    simulate.mockResolvedValueOnce({ ...simulated, credibility: burmeseCredibility, result: inBurmese(simulated.result) });
    // The real path: MetaProvider and useApi hand the view Burmese from the twins.
    render(
      <InBurmese>
        <MetaProvider>
          <Future />
        </MetaProvider>
      </InBurmese>,
    );

    const heading = await screen.findByRole("heading", { name: /ပေါင်းစပ် ဖွံ့ဖြိုးမှု ညွှန်းကိန်း: အာဏာသိမ်းမှု မရှိ၊ 2026/ });
    const chart = heading.closest("figure");
    if (!chart) throw new Error("The chart heading is not inside its figure");
    const picker = screen.getByRole("group", { name: "တည်ငြိမ်မှု လမ်းကြောင်း" });
    expect(within(picker).getByText("အာဏာသိမ်းမှု မရှိ")).toBeVisible();
    expect(within(picker).getByText("လက်ရှိအတိုင်း ဆက်လက်")).toBeVisible();
    expect(screen.getByLabelText("ပညာရေး အသုံးစရိတ်")).toBeInTheDocument();
    expect(screen.queryByText(/No coup|Actual continuation|Education spending|Myanmar/)).not.toBeInTheDocument();

    // Every caveat, in Burmese.
    const note = screen.getByRole("note");
    expect(within(note).getByText("ဖြစ်နိုင်ခြေ အခြေအနေများ၊ ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ")).toBeVisible();
    expect(within(note).getByText("ဖော်ပြထားသော ယူဆချက်များအောက်ရှိ ဖြစ်နိုင်ခြေ အခြေအနေများ။")).toBeVisible();
    expect(within(screen.getByRole("alert")).getByText(NOT_CREDIBLE_MY)).toBeVisible();
    expect(within(chart).getByText("သရုပ်ပြ ရွေ့လျားပုံ")).toBeVisible();
    expect(within(chart).getByText("ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းသာ ပါဝင်")).toBeVisible();
    expect(document.documentElement.lang).toBe("my");
  });

  it("marks a credible run as a scenario, not a forecast", async () => {
    const credible = { ...credibility, credible: true, message: null };
    simulate.mockResolvedValueOnce({ ...simulated, credibility: credible });
    precomputed.mockResolvedValueOnce({ ...scenarios, credibility: credible });
    renderFuture();

    const chart = await findChart();
    expect(within(chart).getByText("Scenario, not a forecast")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import type { Meta, ScenarioResult, ScenariosResponse, SDCredibility, SimulateResponse } from "../api/types";
import { MetaContext } from "../context/metaContext";
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
  framing: FRAMING,
  composition_gap: 0.027,
  last_observed_year: 2024,
  unidentified: ["connectivity_tfp", "savings_rate"],
  unidentified_labels: ["the connectivity effect", "the savings rate"],
  profile_flat: true,
  metrics: [],
};

function result(name: string, label: string): ScenarioResult {
  return {
    name,
    label,
    description: `${label} description`,
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

const simulate = vi.fn();
const precomputed = vi.fn(() => Promise.resolve(scenarios));
vi.mock("../api/client", async (original) => ({
  ...(await original<typeof import("../api/client")>()),
  api: { scenarios: () => precomputed(), simulate: (...args: unknown[]) => simulate(...args) },
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

describe("Future", () => {
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

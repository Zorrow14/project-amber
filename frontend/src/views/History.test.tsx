import { render, screen, within } from "@testing-library/react";

import type { DivergenceResponse, Meta } from "../api/types";
import type { ApiState } from "../hooks/useApi";
import { DivergencePanel } from "./History";

// The honesty guard for the historical arc: a divergence payload must render
// the "illustrative scenario, not a causal estimate" banner, point to the
// Counterfactual view for the rigorous estimate, and never call itself one.

const FRAMING =
  "Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a comparator's actual growth rates. It shows how far the two paths diverged, not what any event cost.";
const POINTER =
  "For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: a fitted synthetic control with placebo tests, scoped to 2021-2024.";

const meta = {
  modeling_window: { start: 2011, end: 2024 },
  historical: {
    window: { start: 1960, end: 2024 },
    countries: [
      { iso3: "MMR", name: "Myanmar", role: "treated" },
      { iso3: "THA", name: "Thailand", role: "comparator" },
    ],
    indicators: [],
    default_indicators: ["NY.GDP.PCAP.KD"],
    default_countries: ["MMR", "THA"],
    comparators: [{ key: "THA", label: "Thailand", units: ["THA"], scenario: "track_thailand", default: true }],
    default_comparator: "THA",
    divergence_anchor: 1960,
    sensitivity_anchors: [1990],
    events: [{ year: 1962, label: "1962 coup" }],
    reliability: [{ country_iso3: "MMR", standard_from: 1990 }],
    framing: {
      divergence: FRAMING,
      low_reliability: "Myanmar before 1990: junta-era national accounts, widely considered unreliable.",
      modeling_window: "The bracket marks the modeling window.",
      rulers: "Constant 2015 US$ throughout.",
      maddison: "Before 1960: Maddison PPP.",
      chained_level: "Levels are chained.",
      fiscal_year: "Fiscal year note.",
      counterfactual_pointer: POINTER,
    },
  },
} as unknown as Meta;

const divergence: DivergenceResponse = {
  scenario: "track_thailand",
  comparator: "THA",
  comparator_label: "Thailand",
  anchor_year: 1960,
  scenario_illustrative: true,
  framing: FRAMING,
  counterfactual_pointer: POINTER,
  notes: ["Nothing is fitted, so there is no p-value or credibility check."],
  series: [
    { year: 1960, actual: 130, path: 130, gap: 0, ratio: 1, n_units: 0, reliability: "low" },
    { year: 1990, actual: 170, path: 577, gap: 407, ratio: 3.39, n_units: 1, reliability: "standard" },
    { year: 2024, actual: 1158, path: 1449, gap: 291, ratio: 1.25, n_units: 1, reliability: "standard" },
  ],
  metrics: {
    anchor_year: 1960,
    anchor_value: 130,
    latest_year: 2024,
    actual_latest: 1158,
    path_latest: 1449,
    gap_latest: 291,
    ratio_latest: 1.251,
    actual_growth_pa: 0.035,
    path_growth_pa: 0.038,
    min_units: 1,
  },
  sensitivity: [
    { anchor_year: 1960, anchor_value: 130, path_latest: 1449, ratio_latest: 1.251, default: true },
    { anchor_year: 1990, anchor_value: 170, path_latest: 428, ratio_latest: 0.369, default: false },
  ],
};

const loaded: ApiState<DivergenceResponse> = {
  data: divergence,
  error: null,
  loading: false,
  waking: false,
  since: null,
  retry: () => {},
};

describe("DivergencePanel", () => {
  it("renders the illustrative-scenario banner for a divergence payload", () => {
    render(<DivergencePanel meta={meta} state={loaded} comparator="THA" onComparator={() => {}} />);

    const banner = screen.getByRole("note");
    expect(within(banner).getByText("Illustrative scenario, not a causal estimate")).toBeVisible();
    expect(within(banner).getByText(/how far the two paths diverged/)).toBeVisible();
    expect(within(banner).getByRole("link", { name: /Counterfactual view/ })).toHaveAttribute(
      "href",
      "#/counterfactual",
    );
    expect(screen.getAllByText("Illustrative scenario").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.25×")[0]).toBeVisible();
    expect(screen.getByText(/Anchor-sensitive: started in 1990 instead/, { selector: "li" })).toBeVisible();
    expect(document.body.textContent?.toLowerCase()).not.toContain("counterfactual estimate");
  });

  it("keeps the banner while the payload is still loading", () => {
    const loading: ApiState<DivergenceResponse> = { ...loaded, data: null, loading: true };
    render(<DivergencePanel meta={meta} state={loading} comparator="THA" onComparator={() => {}} />);

    expect(within(screen.getByRole("note")).getByText("Illustrative scenario, not a causal estimate")).toBeVisible();
  });
});

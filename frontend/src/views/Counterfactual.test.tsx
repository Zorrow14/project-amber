import { render, screen, within } from "@testing-library/react";

import type { Meta, OutcomeResult } from "../api/types";
import { localize } from "../i18n/localize";
import { InBurmese } from "../test/i18n";
import { twin } from "../test/twin";
import { OutcomeSection } from "./Counterfactual";

// The honesty guard: an outcome the API marks credible=false must render the
// not-credible banner and must not present its gap as an effect.

const NOT_CREDIBLE =
  "This gap is not a credible effect estimate: synthetic Myanmar does not track real Myanmar before the coup, so the chart is illustrative only.";
/** The API's Burmese twin of NOT_CREDIBLE (amber.i18n.MY). */
const NOT_CREDIBLE_MY =
  "ဤကွာဟချက်သည် ယုံကြည်ထိုက်သော သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ: အာဏာသိမ်းမှု မတိုင်မီ ပေါင်းစပ်မြန်မာသည် အမှန်တကယ် မြန်မာနှင့် ကိုက်ညီစွာ မလိုက်ပါသောကြောင့် ဤဇယားသည် သရုပ်ပြရန်သာ ဖြစ်သည်။";

const meta = {
  treatment_year: 2021,
  modeling_window: { start: 2011, end: 2024 },
  covid_years: [2020],
  countries: [
    { iso3: "MMR", name: "Myanmar", name_i18n: twin("Myanmar", "မြန်မာ"), treated: true, donor: false },
    { iso3: "KHM", name: "Cambodia", name_i18n: twin("Cambodia", "ကမ္ဘောဒီးယား"), treated: false, donor: true },
    { iso3: "BGD", name: "Bangladesh", name_i18n: twin("Bangladesh", "ဘင်္ဂလားဒေ့ရှ်"), treated: false, donor: true },
  ],
  thresholds: { sc_placebo_poor_fit_multiple: 5 },
  framing: { fiscal_year: "Myanmar's WDI year runs October-September." },
  framing_i18n: { fiscal_year: twin("Myanmar's WDI year runs October-September.", "မြန်မာ၏ WDI နှစ်သည် အောက်တိုဘာမှ စက်တင်ဘာအထိ ဖြစ်သည်။") },
} as unknown as Meta;

const outcome: OutcomeResult = {
  outcome: "combined",
  label: "Combined development index",
  label_i18n: twin("Combined development index"),
  units: "Index points",
  units_i18n: twin("Index points"),
  is_currency: false,
  credibility: {
    credible: false,
    pre_rmse_share: 0.236,
    threshold: 0.1,
    message: NOT_CREDIBLE,
    message_i18n: twin(NOT_CREDIBLE),
  },
  metrics: {
    pre_rmse: 0.085,
    post_rmse: 0.018,
    rmse_ratio: 0.21,
    pre_rmse_share: 0.236,
    pseudo_p_value: 1,
    p_value_floor: 1 / 7,
    rank: 7,
    n_units: 7,
    n_effective_donors: 1.68,
    n_weighted_donors: 2,
    intime_rmse_ratio: 0.81,
    loo_max_deviation: 0.05,
  },
  series: [
    { year: 2020, actual: 0.49, synthetic: 0.5, gap: -0.01 },
    { year: 2024, actual: 0.52, synthetic: 0.55, gap: -0.026 },
  ],
  latest: { year: 2024, actual: 0.52, synthetic: 0.55, gap: -0.026 },
  latest_gap_share: -0.047,
  weights: [
    { donor_iso3: "BGD", donor_name: "Bangladesh", donor_name_i18n: twin("Bangladesh"), weight: 0.72 },
    { donor_iso3: "KHM", donor_name: "Cambodia", donor_name_i18n: twin("Cambodia"), weight: 0.28 },
  ],
  placebos: [
    {
      unit_iso3: "MMR",
      unit_name: "Myanmar",
      unit_name_i18n: twin("Myanmar"),
      treated: true,
      pre_rmse: 0.085,
      poor_fit: false,
      gaps: [],
    },
  ],
  placebo_time: { placebo_year: 2017, series: [] },
  leave_one_out: [],
  leave_one_out_band: [],
};

describe("OutcomeSection", () => {
  it("renders the not-credible banner and withholds the gap for a credible:false payload", () => {
    render(<OutcomeSection outcome={outcome} meta={meta} />);

    const banner = screen.getByRole("alert");
    expect(within(banner).getByText("Not a credible effect estimate")).toBeVisible();
    expect(within(banner).getByText(NOT_CREDIBLE)).toBeVisible();
    expect(screen.getAllByText("Illustrative only").length).toBeGreaterThan(0);
    expect(screen.getByText(/gap is not reported/)).toBeVisible();
    expect(screen.queryByText(/2024 gap: /)).not.toBeInTheDocument();
  });

  it("renders the same verdict in Burmese, from the API's twin, and still withholds the gap", () => {
    const burmese: OutcomeResult = {
      ...outcome,
      label_i18n: twin(outcome.label, "ပေါင်းစပ် ဖွံ့ဖြိုးမှု ညွှန်းကိန်း"),
      credibility: { ...outcome.credibility, message_i18n: twin(NOT_CREDIBLE, NOT_CREDIBLE_MY) },
    };
    // What useApi hands a view in Burmese mode: every display field from its twin.
    render(
      <InBurmese>
        <OutcomeSection outcome={localize(burmese, "my")} meta={localize(meta, "my")} />
      </InBurmese>,
    );

    const banner = screen.getByRole("alert");
    expect(within(banner).getByText("ယုံကြည်ထိုက်သော သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ")).toBeVisible();
    expect(within(banner).getByText(NOT_CREDIBLE_MY)).toBeVisible();
    expect(screen.getAllByText("သရုပ်ပြရန်သာ").length).toBeGreaterThan(0);
    expect(screen.getByText(/2024 ကွာဟချက်ကို မဖော်ပြပါ/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "ပေါင်းစပ် ဖွံ့ဖြိုးမှု ညွှန်းကိန်း" })).toBeVisible();
    expect(screen.queryByText(NOT_CREDIBLE)).not.toBeInTheDocument();
    expect(screen.queryByText("Myanmar")).not.toBeInTheDocument();
  });

  it("shows no banner for a credible payload", () => {
    const credible = { ...outcome, credibility: { ...outcome.credibility, credible: true, message: null } };
    render(<OutcomeSection outcome={credible} meta={meta} />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/2024 gap: /)).toBeVisible();
  });
});

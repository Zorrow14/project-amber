import { render, screen, within } from "@testing-library/react";

import type { DivergenceResponse, Meta } from "../api/types";
import type { ApiState } from "../hooks/useApi";
import { localize } from "../i18n/localize";
import { InBurmese } from "../test/i18n";
import { twin } from "../test/twin";
import { DivergencePanel } from "./History";

// The honesty guard for the historical arc: a divergence payload must render
// the "illustrative scenario, not a causal estimate" banner, point to the
// Counterfactual view for the rigorous estimate, and never call itself one.

const FRAMING =
  "Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a comparator's actual growth rates. It shows how far the two paths diverged, not what any event cost.";
const POINTER =
  "For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: a fitted synthetic control with placebo tests, scoped to 2021-2024.";
/** The API's Burmese twins of FRAMING and POINTER (amber.i18n.MY). */
const FRAMING_MY =
  "သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေသာ ဖြစ်ပြီး အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ: မြန်မာ၏ အမှန်တကယ် အဆင့်ကို နှိုင်းယှဉ်ရာ နိုင်ငံ၏ အမှန်တကယ် တိုးတက်နှုန်းများဖြင့် တိုးပွားစေထားခြင်း ဖြစ်သည်။ လမ်းကြောင်းနှစ်ခု မည်မျှ ကွဲပြားသွားသည်ကို ပြသခြင်းသာ ဖြစ်ပြီး မည်သည့်ဖြစ်ရပ်က မည်မျှ ဆုံးရှုံးစေခဲ့သည်ကို ပြသခြင်း မဟုတ်ပါ။";
const POINTER_MY =
  "2021 အာဏာသိမ်းမှုက မည်သည်ကို ပြောင်းလဲစေခဲ့သည်ကို တိကျခိုင်မာစွာ ခန့်မှန်းတွက်ချက်ထားမှုအတွက် 'မဖြစ်ခဲ့လျှင်' စာမျက်နှာကို ကြည့်ပါ: ပလာစီဘို စမ်းသပ်မှုများ ပါဝင်သော ကိုက်ညီအောင် ချိန်ညှိထားသည့် ပေါင်းစပ်ထိန်းချုပ်မှု ဖြစ်ပြီး 2021-2024 ကိုသာ နယ်ပယ်ထားသည်။";

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
  comparator_label_i18n: twin("Thailand"),
  anchor_year: 1960,
  scenario_illustrative: true,
  framing: FRAMING,
  framing_i18n: twin(FRAMING),
  counterfactual_pointer: POINTER,
  counterfactual_pointer_i18n: twin(POINTER),
  notes: ["Nothing is fitted, so there is no p-value or credibility check."],
  notes_i18n: [twin("Nothing is fitted, so there is no p-value or credibility check.")],
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
      "/?view=counterfactual",
    );
    expect(screen.getAllByText("Illustrative scenario").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.25×")[0]).toBeVisible();
    expect(screen.getByText(/Anchor-sensitive: started in 1990 instead/, { selector: "li" })).toBeVisible();
    expect(document.body.textContent?.toLowerCase()).not.toContain("counterfactual estimate");
  });

  it("renders the illustrative banner in Burmese, still pointing to the Counterfactual view", () => {
    const burmese: DivergenceResponse = {
      ...divergence,
      comparator_label_i18n: twin("Thailand", "ထိုင်း"),
      framing_i18n: twin(FRAMING, FRAMING_MY),
      counterfactual_pointer_i18n: twin(POINTER, POINTER_MY),
    };
    const burmeseMeta = {
      ...meta,
      historical: {
        ...meta.historical,
        countries: [
          { iso3: "MMR", name: "Myanmar", name_i18n: twin("Myanmar", "မြန်မာ"), role: "treated" },
          { iso3: "THA", name: "Thailand", name_i18n: twin("Thailand", "ထိုင်း"), role: "comparator" },
        ],
        comparators: [
          {
            key: "THA",
            label: "Thailand",
            label_i18n: twin("Thailand", "ထိုင်း"),
            units: ["THA"],
            scenario: "track_thailand",
            default: true,
          },
        ],
      },
    } as unknown as Meta;
    render(
      <InBurmese>
        <DivergencePanel
          meta={localize(burmeseMeta, "my")}
          state={{ ...loaded, data: localize(burmese, "my") }}
          comparator="THA"
          onComparator={() => {}}
        />
      </InBurmese>,
    );

    const banner = screen.getByRole("note");
    const title = "သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေသာ ဖြစ်ပြီး အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ";
    expect(within(banner).getByText(title)).toBeVisible();
    // The body is the API's framing with its leading title taken off, as in English.
    expect(within(banner).getByText(/^မြန်မာ၏ အမှန်တကယ် အဆင့်ကို/)).toBeVisible();
    expect(within(banner).getByRole("link", { name: /မဖြစ်ခဲ့လျှင်/ })).toHaveAttribute("href", "/?view=counterfactual");
    expect(screen.getAllByText("သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.25×")[0]).toBeVisible(); // Western numerals in both languages
    expect(document.body.textContent).not.toMatch(/Illustrative|Thailand|Myanmar/);
  });

  it("keeps the banner while the payload is still loading", () => {
    const loading: ApiState<DivergenceResponse> = { ...loaded, data: null, loading: true };
    render(<DivergencePanel meta={meta} state={loading} comparator="THA" onComparator={() => {}} />);

    expect(within(screen.getByRole("note")).getByText("Illustrative scenario, not a causal estimate")).toBeVisible();
  });
});

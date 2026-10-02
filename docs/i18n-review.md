# Burmese translation review

Amber's interface is in English and Burmese (မြန်မာ). Most of the Burmese is a **machine-assisted first pass**. The strings below are the exception that cannot be left to it: the caveats that keep Amber honest, and the few labels that name political events. They are marked `human-verify` and must be checked by a Burmese speaker before they are trusted.

Until every flag is cleared, the Burmese footer says so on every page: the translation is a first pass, and where it is unclear the English is authoritative.

## What to check

1. **Same claim, same strength.** Each caveat has to say exactly what the English says, no more and no less. These distinctions carry the meaning:
   - a *scenario* is not a *forecast*;
   - an *estimate* is not a *forecast*;
   - an *illustrative* path is not a *causal estimate*;
   - a gap that is *not credible* is no estimate at all, not a weak one.
2. **Neutral tone.** The English is even-handed and takes no side. The Burmese must not add loaded or partisan wording, especially for the 1962 and 2021 coups and the 1988 uprising.
3. **Consistent terms.** Each key term should be translated the same way everywhere (see the glossary below).
4. **Unicode only.** The text must be Unicode Burmese, never Zawgyi. If it shows as broken glyphs in a Unicode font, it is in the wrong encoding.
5. **Western digits.** Numerals stay Western (2021, not ၂၀၂၁). This is a deliberate choice, explained below; please do not convert them.

## How to sign a string off

- **App strings** (table B): in `frontend/src/i18n/locales/my.json`, edit the Burmese, then change that key's `_review` value from `"human-verify"` to `"verified"`.
- **API strings** (table A): in `src/amber/i18n.py`, edit the Burmese in `MY`, then remove the English line from `REVIEW`.
- **The footer note** disappears once nothing is pending in either list.
- **Checks:** run `make test`. It confirms both files have the same keys and placeholders, that the Burmese is Unicode, and that no Myanmar digits slipped in.

Table A is keyed by the English text itself. If someone later edits an English caveat, its Burmese stops matching and the API refuses to start, so the string comes back for translation and review. A stale Burmese caveat cannot ship silently.

## Glossary of key terms

| English | Burmese used | Note |
|---|---|---|
| coup | အာဏာသိမ်းမှု | Factual, neutral. |
| counterfactual (the view) | မဖြစ်ခဲ့လျှင် | "Had it not happened." |
| counterfactual estimate | မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှု | Reserved for the synthetic control. |
| synthetic control / synthetic Myanmar | ပေါင်းစပ်ထိန်းချုပ်မှု / ပေါင်းစပ် မြန်မာ | A weighted blend of peer countries. |
| scenario | ဖြစ်နိုင်ခြေ အခြေအနေ | |
| forecast | ကြိုတင်ဟောကိန်း | Kept apart from "estimate", which is ခန့်မှန်းတွက်ချက်မှု. |
| estimate | ခန့်မှန်းတွက်ချက်မှု | |
| causal estimate | အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု | |
| illustrative | သရုပ်ပြ | |
| credible (a fit) | ယုံကြည်ထိုက်သော | Model credibility. |
| reliability (data) | စိတ်ချရမှု | Data quality; kept apart from credibility on purpose. |
| indicator / index / pillar | ညွှန်ပြချက် / ညွှန်းကိန်း / မဏ္ဍိုင် | ညွှန်ပြချက် rather than ညွှန်ကိန်း, so "indicator" never looks like "index". |
| coverage (partial) | ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းသာ ပါဝင် | |
| modeling window | မော်ဒယ်ကာလ | A scope choice, not data quality. |
| lever | ထိန်းညှိချက် | |
| donor pool / donors | နှိုင်းယှဉ်နိုင်ငံ အုပ်စု / နှိုင်းယှဉ်နိုင်ငံများ | |
| placebo | ပလာစီဘို | |
| gap | ကွာဟချက် | |

Proper names stay in their published form:
- the World Bank, World Development Indicators and WDI;
- the Maddison Project and its citation;
- the MSDP;
- *kappa*, *p-value*, p10/p90 and convex.

## Decisions to know about

- **Numerals: Western in both languages.** This covers chart axes, tooltips, stat callouts, tables and years.
  - Technical and financial writing in Myanmar reads Western digits everywhere, and it keeps the charts legible.
  - Labels and units are translated; digits are not.
  - The formatters are pinned to `en-US`, which matters because the `my` locale would otherwise switch to Myanmar digits.
- **Font:** Noto Sans Myanmar (Google Fonts, SIL OFL 1.1), self-hosted. Only its Myanmar face is registered, so Latin text and digits stay in Inter, and the font downloads only when Burmese is on screen.
- **Left in English on purpose:**
  - the API's own validation messages (shown after a translated title);
  - the Maddison citation;
  - the data-source names in the footer.

## Strings awaiting review

### A. Caveat wording the API sends (`src/amber/i18n.py`, `REVIEW`)

| # | Why | English (source) | Burmese (first pass) |
|---|---|---|---|
| A1 | honesty | Scenarios, not forecasts: each shows how the model's assumptions play out, not what will happen. | ဖြစ်နိုင်ခြေ အခြေအနေများ၊ ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ: တစ်ခုချင်းစီသည် မော်ဒယ်၏ ယူဆချက်များ မည်သို့ ဖြစ်ပေါ်လာမည်ကို ပြသခြင်းသာ ဖြစ်ပြီး အမှန်တကယ် ဖြစ်လာမည့်အရာကို ပြသခြင်း မဟုတ်ပါ။ |
| A2 | honesty | Illustrative dynamics, not a calibrated projection: the model's backtest error exceeds its credibility threshold. | သရုပ်ပြ ရွေ့လျားပုံသာ ဖြစ်ပြီး ချိန်ညှိထားသော ရှေ့ဆက်တွက်ချက်မှု မဟုတ်ပါ: မော်ဒယ်၏ နောက်ပြန်စစ်ဆေးမှု အမှားသည် ယုံကြည်ထိုက်မှု သတ်မှတ်ချက်ထက် ကျော်လွန်နေသည်။ |
| A3 | honesty | This gap is not a credible effect estimate: synthetic Myanmar does not track real Myanmar before the coup, so the chart is illustrative only. | ဤကွာဟချက်သည် ယုံကြည်ထိုက်သော သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ: အာဏာသိမ်းမှု မတိုင်မီ ပေါင်းစပ်မြန်မာသည် အမှန်တကယ် မြန်မာနှင့် ကိုက်ညီစွာ မလိုက်ပါသောကြောင့် ဤဇယားသည် သရုပ်ပြရန်သာ ဖြစ်သည်။ |
| A4 | honesty | Hollow points are computed from fewer than all index indicators; part of any movement there is a change of composition, not of development. | အလယ်ဟင်းလင်း အစက်များကို ညွှန်းကိန်း၏ ညွှန်ပြချက်အားလုံး မပါဘဲ တွက်ချက်ထားသည်။ ထိုနေရာရှိ အပြောင်းအလဲ၏ တစ်စိတ်တစ်ပိုင်းသည် ဖွံ့ဖြိုးမှု ပြောင်းလဲခြင်း မဟုတ်ဘဲ ပါဝင်ဖွဲ့စည်းပုံ ပြောင်းလဲခြင်း ဖြစ်သည်။ |
| A5 | honesty | Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a comparator's actual growth rates. It shows how far the two paths diverged, not what any event cost. | သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေသာ ဖြစ်ပြီး အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ: မြန်မာ၏ အမှန်တကယ် အဆင့်ကို နှိုင်းယှဉ်ရာ နိုင်ငံ၏ အမှန်တကယ် တိုးတက်နှုန်းများဖြင့် တိုးပွားစေထားခြင်း ဖြစ်သည်။ လမ်းကြောင်းနှစ်ခု မည်မျှ ကွဲပြားသွားသည်ကို ပြသခြင်းသာ ဖြစ်ပြီး မည်သည့်ဖြစ်ရပ်က မည်မျှ ဆုံးရှုံးစေခဲ့သည်ကို ပြသခြင်း မဟုတ်ပါ။ |
| A6 | honesty | Myanmar before 1990: junta-era national accounts, widely considered unreliable. | 1990 မတိုင်မီ မြန်မာ: စစ်အစိုးရခေတ် အမျိုးသားဝင်ငွေ စာရင်းများ ဖြစ်ပြီး စိတ်မချရဟု ကျယ်ကျယ်ပြန့်ပြန့် ယူဆကြသည်။ |
| A7 | honesty | The bracket marks the modeling window (2011 on): a scope choice for the index, counterfactual and scenarios, not a data-quality flag - that is the hatching. | ကွင်းခတ် အမှတ်အသားသည် မော်ဒယ်ကာလ (2011 မှစ၍) ကို ပြသည်: ညွှန်းကိန်း၊ မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှုနှင့် ဖြစ်နိုင်ခြေ အခြေအနေများအတွက် နယ်ပယ် ရွေးချယ်မှု ဖြစ်ပြီး ဒေတာ အရည်အသွေး အမှတ်အသား မဟုတ်ပါ - ထိုအရာမှာ မျဉ်းစောင်းခြစ်ထားခြင်း ဖြစ်သည်။ |
| A8 | honesty | For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: a fitted synthetic control with placebo tests, scoped to 2021-2024. | 2021 အာဏာသိမ်းမှုက မည်သည်ကို ပြောင်းလဲစေခဲ့သည်ကို တိကျခိုင်မာစွာ ခန့်မှန်းတွက်ချက်ထားမှုအတွက် 'မဖြစ်ခဲ့လျှင်' စာမျက်နှာကို ကြည့်ပါ: ပလာစီဘို စမ်းသပ်မှုများ ပါဝင်သော ကိုက်ညီအောင် ချိန်ညှိထားသည့် ပေါင်းစပ်ထိန်းချုပ်မှု ဖြစ်ပြီး 2021-2024 ကိုသာ နယ်ပယ်ထားသည်။ |
| A9 | honesty | Nothing is fitted, so there is no p-value or credibility check. | မည်သည့်အရာကိုမျှ ကိုက်ညီအောင် ချိန်ညှိထားခြင်း မရှိသောကြောင့် p-value သို့မဟုတ် ယုံကြည်ထိုက်မှု စစ်ဆေးချက် မရှိပါ။ |
| A10 | honesty | The path starts at Myanmar's actual {year} level, itself low reliability. | လမ်းကြောင်းသည် မြန်မာ၏ အမှန်တကယ် {year} အဆင့်မှ စတင်ပြီး ထိုအဆင့်ကိုယ်တိုင် စိတ်ချရမှု နည်းသည်။ |
| A11 | honesty | This scenario leaves the no-coup path before {year}, so the synthetic control is not its reference. | ဤဖြစ်နိုင်ခြေ အခြေအနေသည် {year} မတိုင်မီ အာဏာသိမ်းမှု မရှိသော လမ်းကြောင်းမှ ခွဲထွက်သွားသောကြောင့် ပေါင်းစပ်ထိန်းချုပ်မှုသည် ၎င်း၏ ကိုးကားစံ မဟုတ်ပါ။ |
| A12 | honesty | The synthetic control for this outcome is not credible, so it is no reference. | ဤရလဒ်အတွက် ပေါင်းစပ်ထိန်းချုပ်မှုသည် ယုံကြည်ထိုက်ခြင်း မရှိသောကြောင့် ကိုးကားစံ မဟုတ်ပါ။ |
| A13 | neutrality | Amber is an analytical instrument, not an argument. It treats the February 2021 coup as a documented event with measurable consequences and takes no partisan stance. Its assumptions - the donor pool, the index weights, the lever ranges - are surfaced as settings rather than baked in. | Amber သည် အငြင်းအခုံ တစ်ခု မဟုတ်ဘဲ ခွဲခြမ်းစိတ်ဖြာရေး ကိရိယာ တစ်ခု ဖြစ်သည်။ 2021 ဖေဖော်ဝါရီ အာဏာသိမ်းမှုကို တိုင်းတာနိုင်သော အကျိုးဆက်များရှိသည့် မှတ်တမ်းတင်ထားသော ဖြစ်ရပ်တစ်ခုအဖြစ် သဘောထားပြီး မည်သည့်ဘက်ကိုမျှ မရပ်တည်ပါ။ ၎င်း၏ ယူဆချက်များ - နှိုင်းယှဉ်နိုင်ငံ အုပ်စု၊ ညွှန်းကိန်း အလေးချိန်များ၊ ထိန်းညှိချက် အပိုင်းအခြားများ - ကို ပုံသေ ထည့်သွင်းထားခြင်း မဟုတ်ဘဲ ပြင်ဆင်နိုင်သော ဆက်တင်များအဖြစ် ဖော်ပြထားသည်။ |
| A14 | neutrality | 1962 coup | 1962 အာဏာသိမ်းမှု |
| A15 | neutrality | 1988 uprising | 1988 လူထုအုံကြွမှု |
| A16 | neutrality | 2021 coup | 2021 အာဏာသိမ်းမှု |
| A17 | neutrality | No coup | အာဏာသိမ်းမှု မရှိ |

### B. Caveat wording in the app (`frontend/src/i18n/locales/my.json`, `_review`)

| # | Key | English (source) | Burmese (first pass) |
|---|---|---|---|
| B1 | `honesty.scenarioTitle` | Scenarios, not forecasts | ဖြစ်နိုင်ခြေ အခြေအနေများ၊ ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ |
| B2 | `honesty.scenarioBadge` | Scenario, not a forecast | ဖြစ်နိုင်ခြေ အခြေအနေ၊ ကြိုတင်ဟောကိန်း မဟုတ်ပါ |
| B3 | `honesty.scenarioSentence` | A scenario, not a forecast. | ဖြစ်နိုင်ခြေ အခြေအနေ တစ်ခုသာ ဖြစ်ပြီး ကြိုတင်ဟောကိန်း မဟုတ်ပါ။ |
| B4 | `honesty.illustrativeDynamics` | Illustrative dynamics | သရုပ်ပြ ရွေ့လျားပုံ |
| B5 | `honesty.sdNotCredibleTitle` | Illustrative dynamics, not a calibrated projection | သရုပ်ပြ ရွေ့လျားပုံသာ ဖြစ်ပြီး ချိန်ညှိထားသော ရှေ့ဆက်တွက်ချက်မှု မဟုတ်ပါ |
| B6 | `honesty.backtestFailed` | Illustrative dynamics only: the model failed its backtest gate. | သရုပ်ပြ ရွေ့လျားပုံသာ: မော်ဒယ်သည် ၎င်း၏ နောက်ပြန်စစ်ဆေးမှု စံကို မဖြတ်ကျော်နိုင်ခဲ့ပါ။ |
| B7 | `honesty.scNotCredibleTitle` | Not a credible effect estimate | ယုံကြည်ထိုက်သော သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ |
| B8 | `honesty.illustrativeOnly` | Illustrative only | သရုပ်ပြရန်သာ |
| B9 | `honesty.illustrativeSuffix` |  (illustrative only) |  (သရုပ်ပြရန်သာ) |
| B10 | `honesty.illustrativeShortSuffix` |  (illustrative) |  (သရုပ်ပြ) |
| B11 | `honesty.fitNotCredible` |  Illustrative only: the pre-coup fit is not credible, so the gap is not an effect estimate. |  သရုပ်ပြရန်သာ: အာဏာသိမ်းမှု မတိုင်မီ ကိုက်ညီမှုသည် ယုံကြည်ထိုက်ခြင်း မရှိသောကြောင့် ကွာဟချက်သည် သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ။ |
| B12 | `honesty.gapNotReported` | The {year} gap is not reported: without a credible pre-{treatment} fit it measures the fit's failure, not an effect. | {year} ကွာဟချက်ကို မဖော်ပြပါ: {treatment} မတိုင်မီ ယုံကြည်ထိုက်သော ကိုက်ညီမှု မရှိဘဲ ၎င်းသည် သက်ရောက်မှုကို မဟုတ်ဘဲ ကိုက်ညီမှု၏ ချို့ယွင်းချက်ကိုသာ တိုင်းတာသည်။ |
| B13 | `honesty.gapNotEffect` | Gap (not an effect) | ကွာဟချက် (သက်ရောက်မှု မဟုတ်) |
| B14 | `honesty.estimateNotForecast` | against synthetic {country}: an estimate, not a forecast | ပေါင်းစပ် {country} နှင့် နှိုင်းယှဉ်ထားခြင်း: ခန့်မှန်းတွက်ချက်မှု ဖြစ်ပြီး ကြိုတင်ဟောကိန်း မဟုတ်ပါ |
| B15 | `honesty.headline` | By {year}, {country}'s real GDP per capita was {gap} ({share}) against a synthetic {country} built from its peers - an estimate against a constructed comparison, not a forecast. | {year} တွင် {country} ၏ လူတစ်ဦးချင်း အစစ်အမှန် ဂျီဒီပီသည် ၎င်း၏ နှိုင်းယှဉ်နိုင်ငံများမှ တည်ဆောက်ထားသော ပေါင်းစပ် {country} နှင့် နှိုင်းယှဉ်လျှင် {gap} ({share}) ရှိခဲ့သည် - တည်ဆောက်ထားသော နှိုင်းယှဉ်ချက်နှင့် တွက်ချက်သည့် ခန့်မှန်းတွက်ချက်မှု ဖြစ်ပြီး ကြိုတင်ဟောကိန်း မဟုတ်ပါ။ |
| B16 | `honesty.notOverlaid` | Phase 3's counterfactual for this series is not credible, so it is not overlaid. | ဤစီးရီးအတွက် အဆင့် 3 ၏ မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှုသည် ယုံကြည်ထိုက်ခြင်း မရှိသောကြောင့် ထပ်ဆင့် မပြပါ။ |
| B17 | `honesty.modelOutputs` | Model outputs under stated assumptions: what they would imply, not what will happen. | ဖော်ပြထားသော ယူဆချက်များအောက်ရှိ မော်ဒယ် ရလဒ်များ: ၎င်းတို့ ညွှန်ပြမည့်အရာ ဖြစ်ပြီး အမှန်တကယ် ဖြစ်လာမည့်အရာ မဟုတ်ပါ။ |
| B18 | `honesty.illustrativeScenarioTitle` | Illustrative scenario, not a causal estimate | သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေသာ ဖြစ်ပြီး အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ |
| B19 | `honesty.illustrativeScenario` | Illustrative scenario | သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေ |
| B20 | `honesty.illustrationNotEstimate` | {path} on the path against {actual} actual - an illustration, not an estimate | လမ်းကြောင်းပေါ်တွင် {path}၊ အမှန်တကယ် {actual} - သရုပ်ပြချက်သာ ဖြစ်ပြီး ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ |
| B21 | `honesty.gapAttributesNoCause` | The shaded gap shows how far the two trajectories separated. It bundles every difference between the two - policy, conflict, prices, measurement - and attributes it to no cause. | အရိပ်ခြယ်ထားသော ကွာဟချက်သည် လမ်းကြောင်းနှစ်ခု မည်မျှ ခွဲထွက်သွားသည်ကို ပြသည်။ ၎င်းတွင် နှစ်ခုကြားရှိ ကွာခြားချက် အားလုံး - မူဝါဒ၊ ပဋိပက္ခ၊ ဈေးနှုန်း၊ တိုင်းတာမှု - ပေါင်းပါဝင်ပြီး မည်သည့် အကြောင်းရင်းကိုမျှ မသတ်မှတ်ပါ။ |
| B22 | `honesty.partialCoverage` | Partial indicator coverage | ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းသာ ပါဝင် |
| B23 | `honesty.partialCoveragePill` | Partial coverage: {share} of indicators | တစ်စိတ်တစ်ပိုင်း ပါဝင်မှု: ညွှန်ပြချက်များ၏ {share} |
| B24 | `honesty.partialFrom` | {country} partial from {year} | {country} - {year} မှစ၍ တစ်စိတ်တစ်ပိုင်း |
| B25 | `honesty.partialActual` | Actual, from partial indicator coverage | အမှန်တကယ်၊ ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းမှ တွက်ချက်ထားသည် |
| B26 | `honesty.hollowSummary` | Hollow points mark scores computed from partial indicator coverage. | အလယ်ဟင်းလင်း အစက်များသည် ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းဖြင့် တွက်ချက်ထားသော ရမှတ်များကို ပြသည်။ |
| B27 | `honesty.hollowHistorySummary` | Hollow history points are scored from partial indicator coverage. | အလယ်ဟင်းလင်း သမိုင်းအစက်များကို ညွှန်ပြချက် တစ်စိတ်တစ်ပိုင်းဖြင့် တွက်ချက်ထားသည်။ |
| B28 | `honesty.lowReliability` | low reliability | စိတ်ချရမှု နည်း |
| B29 | `honesty.lowReliabilityBefore` | {country} before {year}: low reliability | {year} မတိုင်မီ {country}: စိတ်ချရမှု နည်း |
| B30 | `honesty.lowReliabilityDotted` | {country} before {year}: low reliability (dotted) | {year} မတိုင်မီ {country}: စိတ်ချရမှု နည်း (အစက်မျဉ်း) |
| B31 | `honesty.lowReliabilitySummary` | {country}'s values before {year} are low reliability, drawn dotted over hatching. | {year} မတိုင်မီ {country} ၏ တန်ဖိုးများသည် စိတ်ချရမှု နည်းပြီး မျဉ်းစောင်းခြစ်ပေါ်တွင် အစက်မျဉ်းဖြင့် ဆွဲထားသည်။ |
| B32 | `honesty.hatched` | Hatched: low-reliability years | မျဉ်းစောင်းခြစ်: စိတ်ချရမှု နည်းသော နှစ်များ |
| B33 | `honesty.windowKey` | Modeling window ({year}+): scope, not data quality | မော်ဒယ်ကာလ ({year}+): နယ်ပယ် သတ်မှတ်ချက် ဖြစ်ပြီး ဒေတာ အရည်အသွေး မဟုတ် |
| B34 | `honesty.windowSummary` | A bracket marks the modeling window from {year}. | ကွင်းခတ် အမှတ်အသားသည် {year} မှစသော မော်ဒယ်ကာလကို ပြသည်။ |
| B35 | `honesty.differentUnits` | Different units ({units}) | မတူညီသော ယူနစ် ({units}) |
| B36 | `charts.coupLong` | Feb {year} coup | {year} ဖေဖော်ဝါရီ အာဏာသိမ်းမှု |
| B37 | `charts.coupShort` | Coup | အာဏာသိမ်းမှု |
| B38 | `charts.illustrativePath` | Illustrative path | သရုပ်ပြ လမ်းကြောင်း |
| B39 | `charts.gapShaded` | Gap, shaded (illustrative) | ကွာဟချက်၊ အရိပ်ခြယ်ထားသည် (သရုပ်ပြ) |
| B40 | `nav.counterfactual` | Counterfactual | မဖြစ်ခဲ့လျှင် |
| B41 | `views.counterfactual.description` | No country shows what {country} would have looked like without the coup, so Amber builds one: a weighted blend of peers that did not rupture in {year}, matched to {country} before it. These are estimates against a constructed comparison, precomputed and never refitted on request. | အာဏာသိမ်းမှု မရှိခဲ့လျှင် {country} မည်သို့ ရှိမည်ကို မည်သည့်နိုင်ငံကမျှ မပြနိုင်သောကြောင့် Amber က တစ်ခု တည်ဆောက်သည်: {year} တွင် ပြိုကွဲမှု မကြုံခဲ့သော နှိုင်းယှဉ်နိုင်ငံများ၏ အလေးချိန် ပေါင်းစပ်မှုကို ထိုမတိုင်မီ {country} နှင့် ကိုက်ညီအောင် ချိန်ညှိထားခြင်း ဖြစ်သည်။ ဤအရာများသည် တည်ဆောက်ထားသော နှိုင်းယှဉ်ချက်နှင့် တွက်ချက်ထားသည့် ခန့်မှန်းတွက်ချက်မှုများ ဖြစ်ပြီး ကြိုတင်တွက်ချက်ထားကာ တောင်းဆိုမှုအလိုက် ဘယ်တော့မှ ပြန်လည်ချိန်ညှိခြင်း မပြုပါ။ |
| B42 | `views.counterfactual.mainNote` | Synthetic {country} is a convex blend of donors fitted to {start}–{end}; after {treatment} the gap between the lines is the estimate. | ပေါင်းစပ် {country} သည် {start}–{end} နှင့် ကိုက်ညီအောင် ချိန်ညှိထားသော နှိုင်းယှဉ်နိုင်ငံများ၏ convex ပေါင်းစပ်မှု ဖြစ်သည်။ {treatment} နောက်ပိုင်း မျဉ်းနှစ်ကြောင်းကြားရှိ ကွာဟချက်သည် ခန့်မှန်းတွက်ချက်မှု ဖြစ်သည်။ |
| B43 | `views.future.inconsistent` | Over {from}–{to} this path runs up to {deviation} from phase 3's synthetic control, beyond the {tolerance} tolerance: read it as optimistic. | {from}–{to} တွင် ဤလမ်းကြောင်းသည် အဆင့် 3 ၏ ပေါင်းစပ်ထိန်းချုပ်မှုမှ {deviation} အထိ ကွာပြီး {tolerance} ခံနိုင်ရည်ကို ကျော်လွန်သည်: အကောင်းမြင်လွန်းသည်ဟု ဖတ်ပါ။ |
| B44 | `views.future.composition` | History scores only the indicators {country} reports (hollow points); scenarios score all of them. In {year} that alone lifts the modeled index by {gap} - a composition step, not a scenario effect. | သမိုင်းသည် {country} ဖော်ပြသော ညွှန်ပြချက်များကိုသာ တွက်ချက်သည် (အလယ်ဟင်းလင်း အစက်များ); ဖြစ်နိုင်ခြေ အခြေအနေများသည် အားလုံးကို တွက်ချက်သည်။ {year} တွင် ထိုအချက် တစ်ခုတည်းက မော်ဒယ် ညွှန်းကိန်းကို {gap} မြှင့်တင်သည် - ပါဝင်ဖွဲ့စည်းပုံ အဆင့်ပြောင်းမှု ဖြစ်ပြီး ဖြစ်နိုင်ခြေ အခြေအနေ၏ သက်ရောက်မှု မဟုတ်ပါ။ |
| B45 | `views.history.sensitivity` | Anchor-sensitive: started in {years} instead, the path ends at {ratios} actual. | အစမှတ်အပေါ် မူတည်သည်: {years} တွင် စတင်ပါက လမ်းကြောင်းသည် အမှန်တကယ်၏ {ratios} ဖြင့် အဆုံးသတ်သည်။ |
| B46 | `views.history.pathLabel` | Tracking {comparator}'s growth since {year} (illustrative) | {year} မှစ၍ {comparator} ၏ တိုးတက်မှုကို လိုက်ခြင်း (သရုပ်ပြ) |
| B47 | `app.translationNote` | This Burmese translation is a machine-assisted first pass. Its caveat wording is awaiting review by a Burmese speaker; where it is unclear, the English is authoritative. | ဤမြန်မာဘာသာပြန်သည် စက်ဖြင့် အကူအညီယူထားသော ပထမမူကြမ်း ဖြစ်သည်။ သတိပေးချက် စကားလုံးများကို မြန်မာစကားပြောသူ တစ်ဦးက ပြန်လည်စစ်ဆေးရန် စောင့်ဆိုင်းနေဆဲ ဖြစ်ပြီး ရှင်းလင်းမှု မရှိသည့်နေရာတွင် အင်္ဂလိပ်မူကို အတည်ယူပါ။ |

The rest of `my.json` and `MY` (navigation, chart labels, explanations) is a first pass too. It is lower stakes, but a reviewer reading the app in Burmese will meet it, and corrections there are just as welcome.

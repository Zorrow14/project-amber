# Burmese translation review

Amber's interface is in English and Burmese (မြန်မာ). Most of the Burmese is a **machine-assisted first pass**. The strings below are the exception that cannot be left to it:
- the caveats that keep Amber honest;
- the few labels that name political events;
- the whole About page, which states how to read Amber honestly, and what each source is used for.

They are marked `human-verify` (draft, pending review) and must be checked by a Burmese speaker before they are trusted.

Until every flag is cleared, the Burmese footer says so on every page: the translation is a first pass, and where it is unclear the English is authoritative. On the About page, each flagged passage also carries its own draft note. So none of this copy is presented as final.

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

- **App strings** (tables B and C): in `frontend/src/i18n/locales/my.json`, edit the Burmese, then change that key's `_review` value from `"human-verify"` to `"verified"`. An About passage's draft note disappears once all the keys it covers are verified.
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

### C. The About page and what each source is used for (`my.json`, `_review`)

The whole About page is a first-pass draft, flagged `human-verify`. In this document that is the *draft, pending review* state. While a passage is flagged, the Burmese page shows a draft note beside it. The rows marked **honesty** or **neutrality** are the ones to read first. Each one has an intent note: what the Burmese must convey, and what it must not.

| # | Key | Kind | Intent | English (source) | Burmese (first pass) |
|---|---|---|---|---|---|
| C1 | `views.about.title` | label | The page title: About Amber. | About Amber | Amber အကြောင်း |
| C2 | `views.about.intro` | framing | States the question neutrally: how Myanmar developed after it began opening up in 2011, and how it might have gone differently. *Opening up* describes the post-2011 reforms; it is not praise. | Amber asks a simple question with a complicated answer: how has Myanmar actually developed since it began opening up in 2011 — and how might things have gone differently? | Amber သည် ရိုးရှင်းသော မေးခွန်းတစ်ခုကို မေးသော်လည်း ၎င်း၏ အဖြေမှာ ရှုပ်ထွေးသည်: မြန်မာနိုင်ငံသည် 2011 တွင် တံခါးဖွင့်စတင်ခဲ့ချိန်မှစ၍ အမှန်တကယ် မည်သို့ ဖွံ့ဖြိုးလာခဲ့သနည်း၊ အခြေအနေများ မည်သို့ ကွဲပြားစွာ ဖြစ်လာနိုင်ခဲ့သနည်း။ |
| C3 | `views.about.lookingTitle` | label | Section heading: what the reader is looking at. | What you're looking at | သင်ကြည့်ရှုနေသည့်အရာ |
| C4 | `views.about.lookingIntro` | label | Three views, each answering a different question. | Three views, three different questions: | စာမျက်နှာ သုံးခု၊ မတူညီသော မေးခွန်း သုံးခု: |
| C5 | `views.about.past` | **honesty** | Past is observed data only, from the World Bank, back to 1960. Nothing in it is modelled or estimated. | What actually happened, reconstructed from real World Bank data (back to 1960). | အမှန်တကယ် ဖြစ်ပျက်ခဲ့သည့်အရာ - World Bank ၏ အစစ်အမှန် ဒေတာများမှ ပြန်လည်တည်ဆောက်ထားသည် (1960 အထိ နောက်ကြောင်းပြန်၍)။ |
| C6 | `views.about.counterfactual` | **honesty** | The Counterfactual is an *estimate* (ခန့်မှန်းတွက်ချက်မှု) of a path without the 2021 coup, made by synthetic control. *Interrupted its democratic transition* is a description, not a verdict: keep it neutral, with no loaded words for the coup. | An estimate of how Myanmar might have developed if the 2021 coup hadn't interrupted its democratic transition, built with a method called synthetic control. | 2021 အာဏာသိမ်းမှုက ၎င်း၏ ဒီမိုကရေစီ အသွင်ကူးပြောင်းမှုကို ကြားဖြတ်ရပ်တန့်စေခြင်း မရှိခဲ့လျှင် မြန်မာနိုင်ငံ မည်သို့ ဖွံ့ဖြိုးလာနိုင်ခဲ့သည်ကို ခန့်မှန်းတွက်ချက်မှု ဖြစ်ပြီး ပေါင်းစပ်ထိန်းချုပ်မှု (synthetic control) ဟုခေါ်သော နည်းလမ်းဖြင့် တည်ဆောက်ထားသည်။ |
| C7 | `views.about.future` | **honesty** | Scenarios that the reader steers. *Might unfold* expresses possibility, not prediction. | Scenarios you steer yourself, adjusting things like stability and investment to see how different paths might unfold. | သင်ကိုယ်တိုင် ထိန်းကျောင်းသော ဖြစ်နိုင်ခြေ အခြေအနေများ - တည်ငြိမ်မှုနှင့် ရင်းနှီးမြှုပ်နှံမှုကဲ့သို့ အရာများကို ချိန်ညှိ၍ မတူညီသော လမ်းကြောင်းများ မည်သို့ ဖြစ်ပေါ်လာနိုင်သည်ကို ကြည့်ရှုနိုင်သည်။ |
| C8 | `views.about.honestyTitle` | label | Heading. *(The important part)* marks this as the section to read. | How to read this honestly (the important part) | ဤအရာကို ရိုးသားစွာ ဖတ်ရှုနည်း (အရေးကြီးဆုံး အပိုင်း) |
| C9 | `views.about.honestyLead` | **honesty** | Amber is for exploring and does not predict the future. The Burmese drops the *crystal ball* idiom but must still say *it does not foretell the future*, not *it cannot be trusted*. | Amber is a tool for exploring, not a crystal ball. | Amber သည် စူးစမ်းလေ့လာရန် ကိရိယာတစ်ခု ဖြစ်ပြီး အနာဂတ်ကို ဟောကိန်းထုတ်ပေးသည့် ကိရိယာ မဟုတ်ပါ။ |
| C10 | `views.about.keepInMind` | label | Lead-in to the two points below it. | Two things to keep in mind: | သတိပြုရမည့် အချက် နှစ်ချက်: |
| C11 | `views.about.estimateLead` | **honesty** | The counterfactual is an *estimate*, not an established fact. It must never read as a *forecast* (ကြိုတင်ဟောကိန်း). | The counterfactual is an estimate, not a fact. | မဖြစ်ခဲ့လျှင် ရလဒ်သည် ခန့်မှန်းတွက်ချက်မှုသာ ဖြစ်ပြီး အမှန်တရား မဟုတ်ပါ။ |
| C12 | `views.about.estimateBody` | **honesty** | Synthetic Myanmar blends similar countries that had no rupture in 2021. The gap is the best estimate of what changed, and it is uncertain; the app shows how uncertain. When the fit fails, Amber says so. Keep *best estimate* modest: not *proof* and not *the effect*. | “Synthetic Myanmar” is built from a blend of similar countries that didn't have a 2021 rupture; the gap between it and the real Myanmar is our best estimate of what changed — but it carries uncertainty, and the app shows you how much. When the method can't fit the data well, Amber says so rather than pretending. | “ပေါင်းစပ် မြန်မာ” ကို 2021 တွင် ပြတ်တောက်မှု မကြုံခဲ့သော ဆင်တူနိုင်ငံများကို ရောစပ်၍ တည်ဆောက်ထားသည်။ ၎င်းနှင့် အမှန်တကယ် မြန်မာအကြား ကွာဟချက်သည် ပြောင်းလဲသွားသည့်အရာအတွက် ကျွန်ုပ်တို့၏ အကောင်းဆုံး ခန့်မှန်းတွက်ချက်မှု ဖြစ်သည် - သို့သော် ၎င်းတွင် မသေချာမှု ပါဝင်ပြီး မည်မျှ ပါဝင်သည်ကို အက်ပ်က ပြသည်။ နည်းလမ်းက ဒေတာနှင့် ကောင်းစွာ ကိုက်ညီအောင် မလုပ်နိုင်သည့်အခါ Amber သည် ဟန်ဆောင်မနေဘဲ ထိုသို့ ပြောပြသည်။ |
| C13 | `views.about.scenarioLead` | **honesty** | Scenarios, not forecasts: the app's central distinction. Use the glossary terms exactly. | The future is scenarios, not forecasts. | အနာဂတ်သည် ဖြစ်နိုင်ခြေ အခြေအနေများသာ ဖြစ်ပြီး ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ။ |
| C14 | `views.about.scenarioBody` | **honesty** | Nothing here predicts what will happen. The Future view follows the reader's chosen assumptions, and every projection is labelled as one. | Nothing here predicts what will happen. The Future view shows what might follow from assumptions you choose. Every projection is labelled as such. | ဤနေရာရှိ မည်သည့်အရာကမျှ ဖြစ်လာမည့်အရာကို ကြိုတင်မဟောပါ။ 'အနာဂတ်' စာမျက်နှာသည် သင်ရွေးချယ်သော ယူဆချက်များမှ ဖြစ်ပေါ်လာနိုင်သည့်အရာကို ပြသည်။ ရှေ့ဆက်တွက်ချက်မှုတိုင်းကို ထိုသို့ အမှတ်အသား ပြုထားသည်။ |
| C15 | `views.about.caveats` | **honesty** | Shaky numbers are flagged, not hidden: thin data, an unreliable fit, old statistics. The caveats are the point, not clutter. *Unreliable fit* is model credibility (ယုံကြည်ထိုက်), which is kept apart from data reliability (စိတ်ချရမှု). | Wherever a number is shaky — thin data, an unreliable fit, an old statistic — Amber flags it rather than hiding it. Those small caveats aren't clutter; they're the point. | ကိန်းဂဏန်းတစ်ခု မခိုင်မာသည့် နေရာတိုင်းတွင် - ဒေတာ နည်းပါးခြင်း၊ ယုံကြည်ထိုက်ခြင်း မရှိသော ကိုက်ညီမှု၊ ဟောင်းနွမ်းသော စာရင်းအင်း - Amber သည် ၎င်းကို ဖုံးကွယ်မထားဘဲ အမှတ်အသား ပြုသည်။ ထိုသတိပေးချက် အသေးလေးများသည် အပိုအရှုပ်များ မဟုတ်ပါ၊ ၎င်းတို့သည် အဓိကအချက် ဖြစ်သည်။ |
| C16 | `views.about.caveatExamples` | label | Screen-reader name of the list of caveat tags. | Caveats you will meet in the app | အက်ပ်တွင် သင်တွေ့ရမည့် သတိပေးချက်များ |
| C17 | `views.about.neutralityTitle` | label | Section heading. | A note on neutrality | ဘက်မလိုက်မှုဆိုင်ရာ မှတ်ချက် |
| C18 | `views.about.neutrality` | **neutrality** | An analytical tool, not an argument. The coup is a documented event with measurable economic consequences, as the data shows, and nothing takes a political side. Every assumption is a control the reader can change. Check that the Burmese takes no side and uses no loaded term for the coup or the military. | This is an analytical tool, not an argument. The 2021 coup is treated as a documented event with measurable economic consequences — which is what the data shows — and nothing here takes a political side. The assumptions behind every estimate are exposed as controls you can change, so you can disagree with them and see what happens. | ဤအရာသည် အငြင်းအခုံ တစ်ခု မဟုတ်ဘဲ ခွဲခြမ်းစိတ်ဖြာရေး ကိရိယာ တစ်ခု ဖြစ်သည်။ 2021 အာဏာသိမ်းမှုကို တိုင်းတာနိုင်သော စီးပွားရေး အကျိုးဆက်များရှိသည့် မှတ်တမ်းတင်ထားသော ဖြစ်ရပ်တစ်ခုအဖြစ် သဘောထားသည် - ဒေတာက ပြသည့်အရာလည်း ထိုအတိုင်း ဖြစ်သည် - ဤနေရာရှိ မည်သည့်အရာကမျှ နိုင်ငံရေးဘက် မလိုက်ပါ။ ခန့်မှန်းတွက်ချက်မှုတိုင်း၏ နောက်ကွယ်ရှိ ယူဆချက်များကို သင်ပြောင်းလဲနိုင်သော ထိန်းညှိချက်များအဖြစ် ဖော်ပြထားသောကြောင့် ၎င်းတို့ကို သဘောမတူပါက ပြောင်းကြည့်ပြီး ဘာဖြစ်လာသည်ကို မြင်နိုင်သည်။ |
| C19 | `views.about.dataTitle` | label | Section heading. | Where the data comes from | ဒေတာ ရင်းမြစ် |
| C20 | `views.about.data` | **honesty** | Data comes from the World Bank, with the IMF as a cross-check only; many series are compiled by UN agencies. **Conflict data (ACLED) is not used**, and the Burmese must not imply that it is. Myanmar's figures before 1990 are flagged as unreliable. Pre-1960 Maddison estimates use another scale and are flagged. | Real indicators come from the World Bank (with the IMF as a cross-check), many of them compiled by UN agencies. Conflict data, such as ACLED's, is not used. Myanmar's figures before 1990 come from an era whose official statistics are widely considered unreliable, so they're marked accordingly. Pre-1960 estimates, where shown, come from the Maddison Project and sit on a different scale — also marked. | အစစ်အမှန် ညွှန်ပြချက်များသည် World Bank မှ ဖြစ်ပြီး (IMF ကို နှိုင်းယှဉ်စစ်ဆေးရန်သာ အသုံးပြုသည်)၊ ၎င်းတို့အနက် အများအပြားကို ကုလသမဂ္ဂ အေဂျင်စီများက စုစည်းထားသည်။ ACLED ကဲ့သို့ ပဋိပက္ခ ဒေတာကို အသုံးမပြုပါ။ 1990 မတိုင်မီ မြန်မာ၏ ကိန်းဂဏန်းများသည် တရားဝင် စာရင်းအင်းများကို စိတ်မချရဟု ကျယ်ကျယ်ပြန့်ပြန့် ယူဆခံရသော ခေတ်မှ ဖြစ်သောကြောင့် ထိုအတိုင်း အမှတ်အသား ပြုထားသည်။ 1960 မတိုင်မီ ခန့်မှန်းချက်များကို ပြသသည့်အခါ ၎င်းတို့သည် Maddison Project မှ ဖြစ်ပြီး မတူညီသော စကေးပေါ်တွင် ရှိသည် - ၎င်းကိုလည်း အမှတ်အသား ပြုထားသည်။ |
| C21 | `views.about.learnTitle` | label | Section heading. | Learn more | ထပ်မံ လေ့လာရန် |
| C22 | `views.about.methodology` | label | Link to the methodology document. | Methodology | နည်းစနစ် |
| C23 | `views.about.limitations` | label | Link to the limitations document. | Limitations | ကန့်သတ်ချက်များ |
| C24 | `views.about.code` | label | Link to the source code on GitHub. | Source code (GitHub) | ရင်းမြစ်ကုဒ် (GitHub) |
| C25 | `views.about.maker` | label | Link to the maker's portfolio. | About the maker | ပြုလုပ်သူ အကြောင်း |
| C26 | `views.about.draft` | **honesty** | Tells a Burmese reader that the passage beside it is a draft translation awaiting a Burmese speaker's review, and that the English is authoritative. It shows only while that passage is flagged. | Draft translation, awaiting review by a Burmese speaker. Where it is unclear, the English is authoritative. | မူကြမ်း ဘာသာပြန် - မြန်မာစကားပြောသူ တစ်ဦး၏ စစ်ဆေးမှုကို စောင့်ဆိုင်းနေဆဲ ဖြစ်သည်။ ရှင်းလင်းမှု မရှိသည့်နေရာတွင် အင်္ဂလိပ်မူကို အတည်ယူပါ။ |
| C27 | `sources.entries.wdi` | **honesty** | Every series comes from WDI. Amber redistributes derived tables under CC BY 4.0, with attribution. | Every series in the app, for every country. Amber's data snapshot redistributes derived tables under this licence, with attribution. | အက်ပ်ရှိ စီးရီးတိုင်း၊ နိုင်ငံတိုင်းအတွက်။ Amber ၏ ဒေတာ snapshot သည် ဆင်းသက်လာသော ဇယားများကို ဤလိုင်စင်အောက်တွင် ရင်းမြစ်ဖော်ပြ၍ ပြန်လည်ဖြန့်ဝေသည်။ |
| C28 | `sources.entries.maddison` | **honesty** | An optional pre-1960 series, on its own axis. It is not bundled, so the published app shows none. | Pre-1960 GDP per capita in the Historical arc, on its own axis. Optional and not bundled, so the published app shows none. | 'သမိုင်းကြောင်း' စာမျက်နှာရှိ 1960 မတိုင်မီ လူတစ်ဦးချင်း GDP ကို ၎င်း၏ ကိုယ်ပိုင် ဝင်ရိုးပေါ်တွင် ပြသည်။ ရွေးချယ်နိုင်ပြီး ထည့်သွင်းထားခြင်း မရှိသောကြောင့် ထုတ်ဝေထားသော အက်ပ်တွင် မပြပါ။ |
| C29 | `sources.entries.undp` | **honesty** | Only the life-expectancy goalposts are cited. No UNDP data is used. | The index's life-expectancy goalposts (20–85 years). The values are cited; no UNDP data is used. | ညွှန်းကိန်း၏ သက်တမ်းရှည်မှု ပန်းတိုင်များ (20–85 နှစ်)။ တန်ဖိုးများကိုသာ ကိုးကားပြီး UNDP ဒေတာကို အသုံးမပြုပါ။ |
| C30 | `sources.entries.sdsn` | **honesty** | Only the under-5 mortality goalposts are cited. No data is used. | The index's under-5 mortality goalposts (2.6–130 per 1,000). The values are cited; no data is used. | ညွှန်းကိန်း၏ 5 နှစ်အောက် ကလေးသေဆုံးနှုန်း ပန်းတိုင်များ (1,000 လျှင် 2.6–130)။ တန်ဖိုးများကိုသာ ကိုးကားပြီး ဒေတာကို အသုံးမပြုပါ။ |
| C31 | `sources.entries.imf` | **honesty** | For comparison only, in the calibration reference. It enters no computation, because it uses a different fiscal year. | Growth figures in the calibration reference, for comparison only. They enter no computation: they use a different fiscal-year basis. | ချိန်ညှိမှု ကိုးကားစာတမ်းရှိ တိုးတက်မှု ကိန်းဂဏန်းများကို နှိုင်းယှဉ်ရန်သာ အသုံးပြုသည်။ မတူညီသော ဘဏ္ဍာရေးနှစ် အခြေခံကို အသုံးပြုသောကြောင့် မည်သည့် တွက်ချက်မှုတွင်မျှ မပါဝင်ပါ။ |
| C32 | `sources.entries.msdp` | **honesty** | Sets the direction of one scenario (Reform push). It is not a data source. | Informs the direction of the Reform push scenario (Strategy 3.7: education and connectivity). | 'ပြုပြင်ပြောင်းလဲရေး တွန်းအား' ဖြစ်နိုင်ခြေ အခြေအနေ၏ ဦးတည်ချက်ကို လမ်းညွှန်သည် (မဟာဗျူဟာ 3.7: ပညာရေးနှင့် ဆက်သွယ်ရေး)။ |
| C33 | `sources.entries.scm` | **honesty** | Names the method behind the Counterfactual view and its placebo checks. | The method behind the Counterfactual view: a weighted blend of peer countries fitted to Myanmar before the coup, checked with placebo tests. | 'မဖြစ်ခဲ့လျှင်' စာမျက်နှာ၏ နောက်ကွယ်ရှိ နည်းလမ်း - အာဏာသိမ်းမှု မတိုင်မီ မြန်မာနှင့် ကိုက်ညီအောင် ချိန်ညှိထားသော နှိုင်းယှဉ်နိုင်ငံများ၏ အလေးချိန်ပေး ရောစပ်မှု ဖြစ်ပြီး ပလာစီဘို စမ်းသပ်မှုများဖြင့် စစ်ဆေးထားသည်။ |
| C34 | `sources.entries.czernich` | **honesty** | The benchmark for one model assumption, nothing more. | The benchmark for the Future model's connectivity-productivity assumption. | အနာဂတ် မော်ဒယ်၏ ဆက်သွယ်ရေး-ကုန်ထုတ်စွမ်းအား ယူဆချက်အတွက် စံနှိုင်းချက်။ |
| C35 | `sources.entries.acled` | **honesty** | **Not used.** The model has no measure of conflict, and the Limitations say what that leaves out. | Not used: the model has no measure of conflict intensity. The Limitations say what that leaves out. | အသုံးမပြုပါ: မော်ဒယ်တွင် ပဋိပက္ခ ပြင်းထန်မှု တိုင်းတာချက် မရှိပါ။ ၎င်းကြောင့် ကျန်ခဲ့သည့်အရာကို 'ကန့်သတ်ချက်များ' တွင် ဖော်ပြထားသည်။ |
| C36 | `sources.entries.hdi` | **honesty** | Not used. The index is built from WDI indicators, not from the published HDI. | Not used: the index is built from WDI indicators, not from the published HDI. | အသုံးမပြုပါ: ညွှန်းကိန်းကို ထုတ်ဝေထားသော HDI မှ မဟုတ်ဘဲ WDI ညွှန်ပြချက်များမှ တည်ဆောက်ထားသည်။ |

The rest of `my.json` and `MY` (navigation, chart labels, explanations) is a first pass too. It is lower stakes, but a reviewer reading the app in Burmese will meet it, and corrections there are just as welcome.

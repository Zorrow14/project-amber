"""Burmese labels for everything the API shows: the config-side label map.

Amber's Python stays English. The UI is bilingual (English default, Burmese),
and every display string the API exposes - country, indicator, pillar, lever and
scenario names, regime markers, and the caveat wording - arrives with a Burmese
twin built from :data:`MY`, so the frontend picks a locale and hardcodes nothing.

:data:`MY` is keyed by the English text itself, verbatim (the gettext model), on
purpose: editing an English caveat in ``config.py`` breaks its lookup, and the API
then refuses to start, so a stale Burmese caveat cannot ship silently. Re-translate
it, and re-flag it in :data:`REVIEW` if it is an honesty string.

Burmese is Unicode only (never Zawgyi), and numerals stay Western in both
languages - ``{year}`` is filled with ``2021``, not ``၂၀၂၁``. Both rules are checked
at import by :func:`_check_i18n`.
"""

from __future__ import annotations

import re
import string
from collections.abc import Mapping
from enum import StrEnum
from typing import Final

__all__ = [
    "DEFAULT_LOCALE",
    "LOCALES",
    "MY",
    "REVIEW",
    "Locale",
    "fill",
    "is_unicode_burmese",
    "text",
]


class Locale(StrEnum):
    """The UI's languages, as BCP 47 tags (also the HTML ``lang`` values)."""

    EN = "en"
    MY = "my"


LOCALES: Final[tuple[Locale, ...]] = tuple(Locale)
DEFAULT_LOCALE: Final[Locale] = Locale.EN


MY: Final[dict[str, str]] = {
    # --- Countries ---------------------------------------------------------- #
    "Myanmar": "မြန်မာ",
    "Vietnam": "ဗီယက်နမ်",
    "Cambodia": "ကမ္ဘောဒီးယား",
    "Bangladesh": "ဘင်္ဂလားဒေ့ရှ်",
    "Lao PDR": "လာအို",
    "Nepal": "နီပေါ",
    "Indonesia": "အင်ဒိုနီးရှား",
    "Thailand": "ထိုင်း",
    # --- Indicators --------------------------------------------------------- #
    "GDP per capita (constant 2015 US$)": "လူတစ်ဦးချင်း ဂျီဒီပီ (2015 ပုံသေဈေး အမေရိကန်ဒေါ်လာ)",
    "GDP growth (annual %)": "ဂျီဒီပီ တိုးနှုန်း (နှစ်စဉ် %)",
    "FDI net inflows (% of GDP)": "နိုင်ငံခြား တိုက်ရိုက်ရင်းနှီးမြှုပ်နှံမှု အသားတင်ဝင်ရောက်မှု (ဂျီဒီပီ၏ %)",
    "Poverty headcount ratio at $2.15/day (% of population)": (
        "တစ်ရက် $2.15 ဆင်းရဲမှုမျဉ်းအောက်ရှိ လူဦးရေ အချိုး (လူဦးရေ၏ %)"
    ),
    "Internet users (% of population)": "အင်တာနက် အသုံးပြုသူ (လူဦးရေ၏ %)",
    "Mobile subscriptions (per 100 people)": "မိုဘိုင်းဖုန်း အသုံးပြုခွင့် (လူ 100 လျှင်)",
    "High-tech exports (% of manufactured exports)": (
        "အဆင့်မြင့်နည်းပညာ ပို့ကုန် (ကုန်ချော ပို့ကုန်၏ %)"
    ),
    "Life expectancy at birth (years)": "မွေးဖွားချိန် ပျမ်းမျှ မျှော်မှန်းသက်တမ်း (နှစ်)",
    "Under-5 mortality (per 1,000 live births)": (
        "ငါးနှစ်အောက် ကလေး သေဆုံးနှုန်း (အရှင်မွေးဖွားမှု 1,000 လျှင်)"
    ),
    "Secondary school enrollment (% gross)": "အလယ်တန်းကျောင်း ကျောင်းအပ်နှံမှု (စုစုပေါင်း %)",
    "Current health expenditure (% of GDP)": "လက်ရှိ ကျန်းမာရေး အသုံးစရိတ် (ဂျီဒီပီ၏ %)",
    "Population, total": "လူဦးရေ၊ စုစုပေါင်း",
    "GDP per capita (2011 int$, PPP; Maddison Project 2023)": (
        "လူတစ်ဦးချင်း ဂျီဒီပီ (2011 နိုင်ငံတကာဒေါ်လာ၊ PPP; Maddison Project 2023)"
    ),
    # --- Why two indicators stay out of the index --------------------------- #
    (
        "Three Myanmar observations (2015-2017), unreported since. In the index it "
        "entered Myanmar's score for those three years only - a composition effect, not "
        "development - and no counterfactual or projection can carry it"
    ): (
        "မြန်မာအတွက် လေ့လာချက် သုံးခုသာ ရှိပြီး (2015-2017) ထို့နောက် ဖော်ပြခြင်း မရှိတော့ပါ။ "
        "ညွှန်းကိန်းတွင် ၎င်းသည် ထိုသုံးနှစ်အတွက်သာ မြန်မာ၏ ရမှတ်ထဲ ပါဝင်ခဲ့သည် - "
        "ဖွံ့ဖြိုးမှု မဟုတ်ဘဲ ပါဝင်ဖွဲ့စည်းပုံ အကျိုးသက်ရောက်မှု ဖြစ်ပြီး မည်သည့် "
        "မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှု သို့မဟုတ် ရှေ့ဆက်တွက်ချက်မှုကမျှ ၎င်းကို "
        "ဆက်လက် ထုတ်ပေး၍ မရပါ"
    ),
    (
        "Erratic for Myanmar (0.2-7.5%) with no structural driver, so no "
        "counterfactual or projection can produce it; in the index it held the innovation "
        "pillar near its floor with noise rather than signal"
    ): (
        "မြန်မာအတွက် မတည်မငြိမ် ဖြစ်ပြီး (0.2-7.5%) ဖွဲ့စည်းပုံဆိုင်ရာ မောင်းနှင်အား "
        "မရှိသောကြောင့် မည်သည့် မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှု သို့မဟုတ် "
        "ရှေ့ဆက်တွက်ချက်မှုကမျှ ၎င်းကို ထုတ်ပေး၍ မရပါ။ ညွှန်းကိန်းတွင် ၎င်းသည် "
        "ဆန်းသစ်တီထွင်မှု မဏ္ဍိုင်ကို အချက်ပြမှုထက် ဆူညံမှုဖြင့် ၎င်း၏ "
        "အနိမ့်ဆုံးအဆင့်အနီးတွင် ထိန်းထားခဲ့သည်"
    ),
    # --- Pillars and model series ------------------------------------------- #
    "Economy": "စီးပွားရေး",
    "Innovation / technology": "ဆန်းသစ်တီထွင်မှု / နည်းပညာ",
    "Human development": "လူ့စွမ်းအား ဖွံ့ဖြိုးမှု",
    "Combined index": "ပေါင်းစပ် ညွှန်းကိန်း",
    "Physical capital per head (2015 US$)": "လူတစ်ဦးချင်း ရုပ်ပိုင်းဆိုင်ရာ အရင်းအနှီး (2015 US$)",
    "Human capital (2011 = 1)": "လူ့အရင်းအနှီး (2011 = 1)",
    "Connectivity: internet users (%)": "ချိတ်ဆက်မှု: အင်တာနက် အသုံးပြုသူ (%)",
    "Institutional stability (reform era = 1)": (
        "အဖွဲ့အစည်းဆိုင်ရာ တည်ငြိမ်မှု (ပြုပြင်ပြောင်းလဲရေးခေတ် = 1)"
    ),
    "Output: GDP per capita (2015 US$)": "ထုတ်လုပ်မှု: လူတစ်ဦးချင်း ဂျီဒီပီ (2015 US$)",
    "the connectivity effect on productivity (kappa)": (
        "ကုန်ထုတ်စွမ်းအားအပေါ် ချိတ်ဆက်မှု၏ သက်ရောက်မှု (kappa)"
    ),
    "the savings rate": "စုငွေနှုန်း",
    # --- Levers ------------------------------------------------------------- #
    "Investment openness": "ရင်းနှီးမြှုပ်နှံမှု ပွင့်လင်းမှု",
    "Investment rate and FDI inflows": (
        "ရင်းနှီးမြှုပ်နှံမှုနှုန်းနှင့် နိုင်ငံခြား တိုက်ရိုက်ရင်းနှီးမြှုပ်နှံမှု ဝင်ရောက်မှု"
    ),
    "Education spending": "ပညာရေး အသုံးစရိတ်",
    "Human-capital accumulation (with health_spend)": (
        "လူ့အရင်းအနှီး စုဆောင်းမှု (ကျန်းမာရေး အသုံးစရိတ်နှင့်အတူ)"
    ),
    "Health spending": "ကျန်းမာရေး အသုံးစရိတ်",
    "Human-capital accumulation and health expenditure % of GDP": (
        "လူ့အရင်းအနှီး စုဆောင်းမှုနှင့် ဂျီဒီပီ၏ % အဖြစ် ကျန်းမာရေး အသုံးစရိတ်"
    ),
    "Connectivity investment": "ချိတ်ဆက်မှု ရင်းနှီးမြှုပ်နှံမှု",
    "The diffusion rate of connectivity": "ချိတ်ဆက်မှု ပျံ့နှံ့နှုန်း",
    # --- Scenarios ---------------------------------------------------------- #
    "Actual continuation": "လက်ရှိအတိုင်း ဆက်လက်",
    "Stability stays at the post-coup level; levers unchanged.": (
        "တည်ငြိမ်မှုသည် အာဏာသိမ်းမှုနောက်ပိုင်း အဆင့်တွင် ဆက်ရှိနေပြီး ထိန်းညှိချက်များ မပြောင်းလဲပါ။"
    ),
    "No coup": "အာဏာသိမ်းမှု မရှိ",
    "Reform-era stability throughout - the counterfactual extended forward.": (
        "ပြုပြင်ပြောင်းလဲရေးခေတ် တည်ငြိမ်မှု တစ်လျှောက်လုံး - "
        "မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှုကို ရှေ့သို့ ဆက်တိုးထားခြင်း။"
    ),
    "Partial recovery": "တစ်စိတ်တစ်ပိုင်း ပြန်လည်နာလန်ထူ",
    "Post-coup stability to 2024, then half the way back by 2035.": (
        "2024 အထိ အာဏာသိမ်းမှုနောက်ပိုင်း တည်ငြိမ်မှု၊ ထို့နောက် 2035 တွင် တစ်ဝက်ခန့် ပြန်လည်ရောက်ရှိ။"
    ),
    "Reform push": "ပြုပြင်ပြောင်းလဲရေး တွန်းအား",
    "No coup, plus the MSDP Strategy 3.7 ambition on education and connectivity.": (
        "အာဏာသိမ်းမှု မရှိ၊ ထို့အပြင် ပညာရေးနှင့် ချိတ်ဆက်မှုဆိုင်ရာ MSDP မဟာဗျူဟာ 3.7 ရည်မှန်းချက်။"
    ),
    "{base}, custom levers": "{base}၊ စိတ်ကြိုက် ထိန်းညှိချက်များ",
    "{base} Levers set by the user.": "{base} ထိန်းညှိချက်များကို အသုံးပြုသူက သတ်မှတ်ထားသည်။",
    # --- Counterfactual outcomes and historical units ----------------------- #
    "Real GDP per capita": "လူတစ်ဦးချင်း အစစ်အမှန် ဂျီဒီပီ",
    "Combined development index": "ပေါင်းစပ် ဖွံ့ဖြိုးမှု ညွှန်းကိန်း",
    "GDP per capita, constant 2015 US$": "လူတစ်ဦးချင်း ဂျီဒီပီ၊ 2015 ပုံသေဈေး အမေရိကန်ဒေါ်လာ",
    "Index points (0.01–1 scale)": "ညွှန်းကိန်း အမှတ် (0.01–1 စကေး)",
    "constant 2015 US$": "2015 ပုံသေဈေး အမေရိကန်ဒေါ်လာ",
    "2011 int$, PPP": "2011 နိုင်ငံတကာဒေါ်လာ၊ PPP",
    # --- Regime markers: what happened, neutrally --------------------------- #
    "1962 coup": "1962 အာဏာသိမ်းမှု",
    "1987 UN LDC status": "1987 ကုလ LDC အဆင့်",
    "1988 uprising": "1988 လူထုအုံကြွမှု",
    "2011 reforms": "2011 ပြုပြင်ပြောင်းလဲမှုများ",
    "2021 coup": "2021 အာဏာသိမ်းမှု",
    "Donor-pool average": "နှိုင်းယှဉ်နိုင်ငံ အုပ်စု ပျမ်းမျှ",
    # --- Framing and caveats ------------------------------------------------ #
    (
        "Amber is an analytical instrument, not an argument. It treats the February 2021 "
        "coup as a documented event with measurable consequences and takes no partisan "
        "stance. Its assumptions - the donor pool, the index weights, the lever ranges - "
        "are surfaced as settings rather than baked in."
    ): (
        "Amber သည် အငြင်းအခုံ တစ်ခု မဟုတ်ဘဲ ခွဲခြမ်းစိတ်ဖြာရေး ကိရိယာ တစ်ခု ဖြစ်သည်။ "
        "2021 ဖေဖော်ဝါရီ အာဏာသိမ်းမှုကို တိုင်းတာနိုင်သော အကျိုးဆက်များရှိသည့် "
        "မှတ်တမ်းတင်ထားသော ဖြစ်ရပ်တစ်ခုအဖြစ် သဘောထားပြီး မည်သည့်ဘက်ကိုမျှ မရပ်တည်ပါ။ "
        "၎င်း၏ ယူဆချက်များ - နှိုင်းယှဉ်နိုင်ငံ အုပ်စု၊ ညွှန်းကိန်း အလေးချိန်များ၊ "
        "ထိန်းညှိချက် အပိုင်းအခြားများ - ကို ပုံသေ ထည့်သွင်းထားခြင်း မဟုတ်ဘဲ "
        "ပြင်ဆင်နိုင်သော ဆက်တင်များအဖြစ် ဖော်ပြထားသည်။"
    ),
    (
        "Scenarios, not forecasts: each shows how the model's assumptions play out, not "
        "what will happen."
    ): (
        "ဖြစ်နိုင်ခြေ အခြေအနေများ၊ ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ: "
        "တစ်ခုချင်းစီသည် မော်ဒယ်၏ ယူဆချက်များ မည်သို့ ဖြစ်ပေါ်လာမည်ကို ပြသခြင်းသာ ဖြစ်ပြီး "
        "အမှန်တကယ် ဖြစ်လာမည့်အရာကို ပြသခြင်း မဟုတ်ပါ။"
    ),
    (
        "Illustrative dynamics, not a calibrated projection: the model's backtest error "
        "exceeds its credibility threshold."
    ): (
        "သရုပ်ပြ ရွေ့လျားပုံသာ ဖြစ်ပြီး ချိန်ညှိထားသော ရှေ့ဆက်တွက်ချက်မှု မဟုတ်ပါ: "
        "မော်ဒယ်၏ နောက်ပြန်စစ်ဆေးမှု အမှားသည် ယုံကြည်ထိုက်မှု သတ်မှတ်ချက်ထက် ကျော်လွန်နေသည်။"
    ),
    (
        "This gap is not a credible effect estimate: synthetic Myanmar does not track real "
        "Myanmar before the coup, so the chart is illustrative only."
    ): (
        "ဤကွာဟချက်သည် ယုံကြည်ထိုက်သော သက်ရောက်မှု ခန့်မှန်းတွက်ချက်မှု မဟုတ်ပါ: "
        "အာဏာသိမ်းမှု မတိုင်မီ ပေါင်းစပ်မြန်မာသည် အမှန်တကယ် မြန်မာနှင့် ကိုက်ညီစွာ "
        "မလိုက်ပါသောကြောင့် ဤဇယားသည် သရုပ်ပြရန်သာ ဖြစ်သည်။"
    ),
    (
        "Myanmar's WDI year runs October-September, so 2021 includes four pre-coup months."
    ): (
        "မြန်မာ၏ WDI နှစ်သည် အောက်တိုဘာမှ စက်တင်ဘာအထိ ဖြစ်သောကြောင့် "
        "2021 တွင် အာဏာသိမ်းမှု မတိုင်မီ လေးလ ပါဝင်သည်။"
    ),
    (
        "Hollow points are computed from fewer than all index indicators; part of any "
        "movement there is a change of composition, not of development."
    ): (
        "အလယ်ဟင်းလင်း အစက်များကို ညွှန်းကိန်း၏ ညွှန်ပြချက်အားလုံး မပါဘဲ တွက်ချက်ထားသည်။ "
        "ထိုနေရာရှိ အပြောင်းအလဲ၏ တစ်စိတ်တစ်ပိုင်းသည် ဖွံ့ဖြိုးမှု ပြောင်းလဲခြင်း မဟုတ်ဘဲ "
        "ပါဝင်ဖွဲ့စည်းပုံ ပြောင်းလဲခြင်း ဖြစ်သည်။"
    ),
    (
        "This scenario leaves the no-coup path before {year}, so the synthetic control is "
        "not its reference."
    ): (
        "ဤဖြစ်နိုင်ခြေ အခြေအနေသည် {year} မတိုင်မီ အာဏာသိမ်းမှု မရှိသော လမ်းကြောင်းမှ "
        "ခွဲထွက်သွားသောကြောင့် ပေါင်းစပ်ထိန်းချုပ်မှုသည် ၎င်း၏ ကိုးကားစံ မဟုတ်ပါ။"
    ),
    "The synthetic control for this outcome is not credible, so it is no reference.": (
        "ဤရလဒ်အတွက် ပေါင်းစပ်ထိန်းချုပ်မှုသည် ယုံကြည်ထိုက်ခြင်း မရှိသောကြောင့် ကိုးကားစံ မဟုတ်ပါ။"
    ),
    # --- Historical arc ----------------------------------------------------- #
    (
        "Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a "
        "comparator's actual growth rates. It shows how far the two paths diverged, not "
        "what any event cost."
    ): (
        "သရုပ်ပြ ဖြစ်နိုင်ခြေ အခြေအနေသာ ဖြစ်ပြီး အကြောင်းရင်း-အကျိုးဆက် ခန့်မှန်းတွက်ချက်မှု "
        "မဟုတ်ပါ: မြန်မာ၏ အမှန်တကယ် အဆင့်ကို နှိုင်းယှဉ်ရာ နိုင်ငံ၏ အမှန်တကယ် "
        "တိုးတက်နှုန်းများဖြင့် တိုးပွားစေထားခြင်း ဖြစ်သည်။ လမ်းကြောင်းနှစ်ခု မည်မျှ "
        "ကွဲပြားသွားသည်ကို ပြသခြင်းသာ ဖြစ်ပြီး မည်သည့်ဖြစ်ရပ်က မည်မျှ ဆုံးရှုံးစေခဲ့သည်ကို "
        "ပြသခြင်း မဟုတ်ပါ။"
    ),
    "Myanmar before 1990: junta-era national accounts, widely considered unreliable.": (
        "1990 မတိုင်မီ မြန်မာ: စစ်အစိုးရခေတ် အမျိုးသားဝင်ငွေ စာရင်းများ ဖြစ်ပြီး "
        "စိတ်မချရဟု ကျယ်ကျယ်ပြန့်ပြန့် ယူဆကြသည်။"
    ),
    (
        "Myanmar is reported on its fiscal-year basis, which moved from April-March to "
        "October-September in 2018."
    ): (
        "မြန်မာကို ၎င်း၏ ဘဏ္ဍာရေးနှစ် အခြေခံဖြင့် ဖော်ပြထားပြီး ထိုဘဏ္ဍာရေးနှစ်သည် "
        "2018 တွင် ဧပြီ-မတ်မှ အောက်တိုဘာ-စက်တင်ဘာသို့ ပြောင်းလဲခဲ့သည်။"
    ),
    (
        "Constant-price levels are chained back from 2015 through every reported growth rate, "
        "so doubtful growth anywhere - the official double-digit rates of the 2000s included - "
        "moves the 1960 anchor."
    ): (
        "ပုံသေဈေး အဆင့်များကို 2015 မှ နောက်ပြန် ဖော်ပြထားသော တိုးနှုန်းတိုင်းဖြင့် "
        "ဆက်စပ်တွက်ချက်ထားသောကြောင့် မည်သည့်နေရာရှိ သံသယဖြစ်ဖွယ် တိုးနှုန်းမဆို - "
        "2000 ပြည့်နှစ်များ၏ တရားဝင် ဂဏန်းနှစ်လုံး တိုးနှုန်းများ အပါအဝင် - "
        "1960 အစမှတ်ကို ရွှေ့စေသည်။"
    ),
    (
        "Constant 2015 US$ throughout; current-US$ series are excluded (exchange-rate artifact)."
    ): (
        "တစ်လျှောက်လုံး 2015 ပုံသေဈေး အမေရိကန်ဒေါ်လာ ဖြစ်သည်။ လက်ရှိဈေး ဒေါ်လာ စီးရီးများကို "
        "ဖယ်ထားသည် (ငွေလဲနှုန်းကြောင့် ဖြစ်ပေါ်သော ပုံပျက်မှု)။"
    ),
    "Before 1960: Maddison PPP (2011 int$), a different ruler on its own axis": (
        "1960 မတိုင်မီ: Maddison PPP (2011 နိုင်ငံတကာဒေါ်လာ)၊ "
        "၎င်း၏ ကိုယ်ပိုင် ဝင်ရိုးပေါ်ရှိ မတူညီသော တိုင်းတာစံ"
    ),
    (
        "The bracket marks the modeling window (2011 on): a scope choice for the index, "
        "counterfactual and scenarios, not a data-quality flag - that is the hatching."
    ): (
        "ကွင်းခတ် အမှတ်အသားသည် မော်ဒယ်ကာလ (2011 မှစ၍) ကို ပြသည်: ညွှန်းကိန်း၊ "
        "မဖြစ်ခဲ့လျှင် ခန့်မှန်းတွက်ချက်မှုနှင့် ဖြစ်နိုင်ခြေ အခြေအနေများအတွက် "
        "နယ်ပယ် ရွေးချယ်မှု ဖြစ်ပြီး ဒေတာ အရည်အသွေး အမှတ်အသား မဟုတ်ပါ - "
        "ထိုအရာမှာ မျဉ်းစောင်းခြစ်ထားခြင်း ဖြစ်သည်။"
    ),
    (
        "For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: "
        "a fitted synthetic control with placebo tests, scoped to 2021-2024."
    ): (
        "2021 အာဏာသိမ်းမှုက မည်သည်ကို ပြောင်းလဲစေခဲ့သည်ကို တိကျခိုင်မာစွာ "
        "ခန့်မှန်းတွက်ချက်ထားမှုအတွက် 'မဖြစ်ခဲ့လျှင်' စာမျက်နှာကို ကြည့်ပါ: "
        "ပလာစီဘို စမ်းသပ်မှုများ ပါဝင်သော ကိုက်ညီအောင် ချိန်ညှိထားသည့် "
        "ပေါင်းစပ်ထိန်းချုပ်မှု ဖြစ်ပြီး 2021-2024 ကိုသာ နယ်ပယ်ထားသည်။"
    ),
    "Nothing is fitted, so there is no p-value or credibility check.": (
        "မည်သည့်အရာကိုမျှ ကိုက်ညီအောင် ချိန်ညှိထားခြင်း မရှိသောကြောင့် "
        "p-value သို့မဟုတ် ယုံကြည်ထိုက်မှု စစ်ဆေးချက် မရှိပါ။"
    ),
    "The path starts at Myanmar's actual {year} level.": (
        "လမ်းကြောင်းသည် မြန်မာ၏ အမှန်တကယ် {year} အဆင့်မှ စတင်သည်။"
    ),
    "The path starts at Myanmar's actual {year} level, itself low reliability.": (
        "လမ်းကြောင်းသည် မြန်မာ၏ အမှန်တကယ် {year} အဆင့်မှ စတင်ပြီး "
        "ထိုအဆင့်ကိုယ်တိုင် စိတ်ချရမှု နည်းသည်။"
    ),
}  # fmt: skip
"""English display text -> Burmese, keyed by the English verbatim (see the module doc)."""


class ReviewReason(StrEnum):
    """Why a translation must be checked by a Burmese speaker before it is trusted."""

    HONESTY = "honesty"
    """A caveat: it must say exactly what the English says - no stronger, no weaker."""
    NEUTRALITY = "neutrality"
    """A political event or framing: the wording must stay even-handed."""


REVIEW: Final[dict[str, ReviewReason]] = {
    english: reason
    for reason, texts in {
        ReviewReason.HONESTY: (
            "Scenarios, not forecasts: each shows how the model's assumptions play out, not "
            "what will happen.",
            "Illustrative dynamics, not a calibrated projection: the model's backtest error "
            "exceeds its credibility threshold.",
            "This gap is not a credible effect estimate: synthetic Myanmar does not track real "
            "Myanmar before the coup, so the chart is illustrative only.",
            "Hollow points are computed from fewer than all index indicators; part of any "
            "movement there is a change of composition, not of development.",
            "Illustrative scenario, not a causal estimate: Myanmar's actual level, grown at a "
            "comparator's actual growth rates. It shows how far the two paths diverged, not "
            "what any event cost.",
            "Myanmar before 1990: junta-era national accounts, widely considered unreliable.",
            "The bracket marks the modeling window (2011 on): a scope choice for the index, "
            "counterfactual and scenarios, not a data-quality flag - that is the hatching.",
            "For a rigorous estimate of what the 2021 coup changed, see the Counterfactual view: "
            "a fitted synthetic control with placebo tests, scoped to 2021-2024.",
            "Nothing is fitted, so there is no p-value or credibility check.",
            "The path starts at Myanmar's actual {year} level, itself low reliability.",
            "This scenario leaves the no-coup path before {year}, so the synthetic control is "
            "not its reference.",
            "The synthetic control for this outcome is not credible, so it is no reference.",
        ),
        ReviewReason.NEUTRALITY: (
            "Amber is an analytical instrument, not an argument. It treats the February 2021 "
            "coup as a documented event with measurable consequences and takes no partisan "
            "stance. Its assumptions - the donor pool, the index weights, the lever ranges - "
            "are surfaced as settings rather than baked in.",
            "1962 coup",
            "1988 uprising",
            "2021 coup",
            "No coup",
        ),
    }.items()
    for english in texts
}
"""Translations flagged ``human-verify``, listed in ``docs/i18n-review.md``. Machine-
assisted Burmese is a first pass; these may not be trusted until a Burmese speaker
has checked them, and the UI says so while any is pending."""


def text(english: str) -> dict[Locale, str]:
    """One display string in every locale.

    Raises:
        KeyError: no Burmese twin - including when the English was edited, which
            is the point: add or re-translate it in :data:`MY`.
    """
    try:
        burmese = MY[english]
    except KeyError:
        raise KeyError(f"No Burmese translation for {english!r}: add it to amber.i18n.MY") from None
    return {Locale.EN: english, Locale.MY: burmese}


def fill(template: str, **values: str | int | Mapping[Locale, str]) -> dict[Locale, str]:
    """A template filled in every locale.

    A value given per locale (``text(...)``) is used in its own language; plain
    values (years) are the same in both, in Western digits.
    """
    localized = text(template)
    return {
        locale: localized[locale].format(
            **{
                key: value[locale] if isinstance(value, Mapping) else str(value)
                for key, value in values.items()
            }
        )
        for locale in LOCALES
    }


_MYANMAR_RUN = re.compile(r"[က-႟]+")
_CORE_BURMESE = re.compile(r"^[က-၏]+$")
_MYANMAR_DIGITS = re.compile(f"[{chr(0x1040)}-{chr(0x1049)}]")
_PRE_BASE = "ေျြ"
"""The vowel sign E and the medials Ya and Ra: in Unicode they follow their
consonant; in Zawgyi they are typed first, so a run starting with one is Zawgyi."""


def is_unicode_burmese(value: str) -> bool:
    """Whether every Myanmar-script run in ``value`` is plausible Unicode Burmese.

    A heuristic, not a converter: it rejects the two Zawgyi tells - a pre-base
    vowel or medial opening a run, and the U+1050-U+109F block Zawgyi borrows for
    stacked forms (Burmese itself needs only U+1000-U+104F).
    """
    runs = _MYANMAR_RUN.findall(value)
    return all(_CORE_BURMESE.match(run) and run[0] not in _PRE_BASE for run in runs)


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _check_i18n(my: Mapping[str, str] = MY, review: Mapping[str, ReviewReason] = REVIEW) -> None:
    """Fail fast on a translation table that cannot be trusted.

    Raises:
        ValueError: an empty translation, a template whose placeholders differ
            between the languages, Burmese that is not Unicode (or has no Myanmar
            script at all), Myanmar digits, or a review flag on an unknown string.
    """
    problems = []
    for english, burmese in my.items():
        if not burmese.strip():
            problems.append(f"{english!r}: empty translation")
        if _fields(english) != _fields(burmese):
            problems.append(f"{english!r}: placeholders {_fields(burmese)} != {_fields(english)}")
        if not _MYANMAR_RUN.search(burmese):
            problems.append(f"{english!r}: translation has no Burmese script")
        if not is_unicode_burmese(burmese):
            problems.append(f"{english!r}: translation is not Unicode Burmese (Zawgyi?)")
        if _MYANMAR_DIGITS.search(burmese):
            problems.append(f"{english!r}: Myanmar digits - numerals stay Western")
    problems += [
        f"{english!r}: flagged for review but not translated"
        for english in review
        if english not in my
    ]
    if problems:
        raise ValueError("Bad Burmese label map:\n" + "\n".join(problems))


_check_i18n()

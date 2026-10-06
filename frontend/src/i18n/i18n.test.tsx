import { act, fireEvent, render, screen, within } from "@testing-library/react";

import { AppShell } from "../components/AppShell";
import { TranslationNote } from "../App";
import { VIEWS } from "../lib/url";
import { formatDollars, formatPercent } from "../lib/format";
import { placeholders, type Messages } from "./catalog";
import { i18nFor, useI18n } from "./context";
import { preferredLocale } from "./detect";
import { I18nProvider } from "./I18nProvider";
import { localize } from "./localize";
import en from "./locales/en.json";
import my from "./locales/my.json";
import { ordinal, rankOf } from "./words";

/** Every message as `dotted.key -> template`. */
function leaves(node: object, prefix = ""): Record<string, string> {
  return Object.fromEntries(
    Object.entries(node).flatMap(([key, value]) =>
      typeof value === "string" ? [[`${prefix}${key}`, value]] : Object.entries(leaves(value as object, `${prefix}${key}.`)),
    ),
  );
}

const { _review: review, ...burmeseCatalog } = my;
const english = leaves(en);
const burmese = leaves(burmeseCatalog);

/** Symbols and placeholders that read the same in both languages. */
const LANGUAGE_NEUTRAL = new Set([
  "app.brand",
  "app.footerCommit",
  "controls.multiplier",
  "charts.band",
  "charts.p10p90",
  "charts.p10",
  "charts.p90",
  "meta.middot",
  "meta.ratio",
  "views.past.weight",
  "views.counterfactual.weight",
  "views.future.readoutScore",
  "views.history.maddisonColumn",
  "export.csv",
  "export.png",
]);

// Unicode Burmese stores the vowel sign E and the medials after their consonant;
// Zawgyi types them first. Burmese needs only U+1000-U+104F (Zawgyi borrows
// U+1050-U+109F for stacked forms), and digits stay Western.
const MYANMAR_RUN = /[က-႟]+/gu;
const isUnicodeBurmese = (text: string) =>
  [...text.matchAll(MYANMAR_RUN)].every(([run]) => /^[က-၏]+$/u.test(run) && !/^[ေျြ]/u.test(run));

describe("the message catalogs", () => {
  it("give Burmese every English key, and no other", () => {
    expect(Object.keys(burmese).sort()).toEqual(Object.keys(english).sort());
  });

  it("keep each message's placeholders in both languages", () => {
    for (const [key, template] of Object.entries(english)) {
      expect([key, placeholders(burmese[key] ?? "").sort()]).toEqual([key, placeholders(template).sort()]);
    }
  });

  it("flag every honesty message for human review, and only real keys", () => {
    const flagged = new Set(Object.keys(review));
    const honesty = Object.keys(english).filter((key) => key.startsWith("honesty."));
    expect(honesty.filter((key) => !flagged.has(key))).toEqual([]);
    expect([...flagged].filter((key) => !(key in english))).toEqual([]);
    // "verified" once a Burmese speaker has signed it off (docs/i18n-review.md).
    expect(Object.values(review).filter((status) => status !== "human-verify" && status !== "verified")).toEqual([]);
  });

  it("flag the whole About page and every source's stated role: a draft, never final", () => {
    const flagged = new Set(Object.keys(review));
    const drafts = Object.keys(english).filter((key) => key.startsWith("views.about.") || key.startsWith("sources.entries."));
    expect(drafts.length).toBeGreaterThan(30);
    expect(drafts.filter((key) => !flagged.has(key))).toEqual([]);
  });

  it("write Burmese in Unicode with Western digits, never repeating the English", () => {
    for (const [key, text] of Object.entries(burmese)) {
      expect([key, isUnicodeBurmese(text)]).toEqual([key, true]);
      expect([key, /[၀-၉]/u.test(text)]).toEqual([key, false]);
      if (!LANGUAGE_NEUTRAL.has(key)) expect([key, text !== english[key]]).toEqual([key, true]);
    }
  });
});

describe("the language", () => {
  it("starts from the browser's preference and falls back to English", () => {
    expect(preferredLocale(["my-MM", "en-US"])).toBe("my");
    expect(preferredLocale(["fr-FR", "en-GB"])).toBe("en");
    expect(preferredLocale(["fr-FR", "my"])).toBe("my");
    expect(preferredLocale(["th-TH"])).toBe("en");
    expect(preferredLocale([])).toBe("en");
  });

  it("puts every display field of a payload in the chosen language, from its twin", () => {
    const payload = {
      name: "Myanmar",
      name_i18n: { en: "Myanmar", my: "မြန်မာ" },
      notes: ["Low reliability."],
      notes_i18n: [{ en: "Low reliability.", my: "စိတ်ချရမှု နည်း။" }],
      framing: { scenario: "Scenarios, not forecasts." },
      framing_i18n: { scenario: { en: "Scenarios, not forecasts.", my: "ဖြစ်နိုင်ခြေ အခြေအနေများ" } },
      message: null,
      message_i18n: null,
      values: [1, 2, 3],
    };
    const burmesePayload = localize(payload, "my");

    expect(burmesePayload.name).toBe("မြန်မာ");
    expect(burmesePayload.notes).toEqual(["စိတ်ချရမှု နည်း။"]);
    expect(burmesePayload.framing.scenario).toBe("ဖြစ်နိုင်ခြေ အခြေအနေများ");
    expect(burmesePayload.message).toBeNull();
    expect(burmesePayload.values).toBe(payload.values); // numbers are untouched
    expect(localize(payload, "en")).toBe(payload);
    expect(localize(payload, "my")).toBe(burmesePayload); // cached: same data, same identity
  });

  it("keeps Western numerals in Burmese: only the words around them change", () => {
    const inBurmese = i18nFor("my", my as Messages);
    const inEnglish = i18nFor("en", en);
    expect(ordinal(inEnglish, 1)).toBe("1st");
    expect(ordinal(inEnglish, 12)).toBe("12th");
    expect(ordinal(inEnglish, 23)).toBe("23rd");
    expect(rankOf(inEnglish, 7, 7)).toBe("7th of 7");
    expect(rankOf(inBurmese, 7, 7)).toBe("7 ခုအနက် အဆင့် 7");
    expect(inBurmese.t("charts.coupLong", { year: 2021 })).toBe("2021 ဖေဖော်ဝါရီ အာဏာသိမ်းမှု");
    // The formatters are locale-free: the same digits whatever the UI language.
    expect(formatDollars(1158)).toBe("$1,158");
    expect(formatPercent(0.67)).toBe("67%");
  });
});

function Shell() {
  const { t } = useI18n();
  const labels = Object.fromEntries(VIEWS.map((view) => [view, t(`nav.${view}`)])) as Record<(typeof VIEWS)[number], string>;
  return (
    <AppShell views={VIEWS} labels={labels} current="overview" footer={<TranslationNote />}>
      <p>{t("honesty.scenarioBadge")}</p>
    </AppShell>
  );
}

describe("the language toggle", () => {
  it("switches every UI string, the document language and back", async () => {
    render(
      <I18nProvider initialLocale="en">
        <Shell />
      </I18nProvider>,
    );
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Historical arc")).toBeVisible();
    expect(screen.getByText("Scenario, not a forecast")).toBeVisible();
    expect(document.documentElement.lang).toBe("en");
    expect(document.querySelector("[data-translation-note]")).toBeNull();

    const toggle = screen.getByRole("group", { name: "Language" });
    const burmeseButton = within(toggle).getByRole("button", { name: "မြန်မာဘာသာ" });
    expect(burmeseButton).toHaveAttribute("lang", "my");
    expect(within(toggle).getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");

    // The Burmese catalog is its own chunk: it loads, then the page switches.
    await act(async () => fireEvent.click(burmeseButton));
    expect(await within(nav).findByText("သမိုင်းကြောင်း")).toBeVisible();
    expect(screen.getByText("ဖြစ်နိုင်ခြေ အခြေအနေ၊ ကြိုတင်ဟောကိန်း မဟုတ်ပါ")).toBeVisible();
    expect(screen.queryByText("Historical arc")).not.toBeInTheDocument();
    expect(document.documentElement.lang).toBe("my");
    expect(burmeseButton).toHaveAttribute("aria-pressed", "true");
    // While any Burmese caveat awaits review, the page says so.
    expect(document.querySelector("[data-translation-note]")).toHaveTextContent("မြန်မာစကားပြောသူ");

    fireEvent.click(within(screen.getByRole("group", { name: "ဘာသာစကား" })).getByRole("button", { name: "English" }));
    expect(await within(nav).findByText("Historical arc")).toBeVisible();
    expect(document.documentElement.lang).toBe("en");
  });
});

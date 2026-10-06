import { render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { App } from "../App";
import { RouteProvider } from "../context/route";
import { I18nProvider } from "../i18n/I18nProvider";
import { InBurmese } from "../test/i18n";
import { About } from "./About";

// About is the landing page and the plain-language statement of how to read
// Amber. Its honesty passages must be on screen in both languages, and while
// their Burmese is a draft, the page must say so beside them.

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("About", () => {
  it("is the default landing view, and renders before /meta answers", async () => {
    // A sleeping API: /meta never answers. About needs nothing from it.
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    render(
      <I18nProvider initialLocale="en">
        <RouteProvider>
          <App />
        </RouteProvider>
      </I18nProvider>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: "About Amber" })).toBeVisible();
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "About" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Future" })).toHaveAttribute("href", "/?view=future");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("Sources & citations");
    expect(screen.getByRole("button", { name: "Copy a link to this view" })).toBeInTheDocument();
  });

  it("says how to read Amber honestly, in English", () => {
    render(<About />);

    const note = screen.getByRole("note");
    expect(within(note).getByText("Amber is a tool for exploring, not a crystal ball.")).toBeVisible();
    expect(within(note).getByText("The counterfactual is an estimate, not a fact.")).toBeVisible();
    expect(within(note).getByText(/When the method can't fit the data well, Amber says so rather than pretending\./)).toBeVisible();
    expect(within(note).getByText("The future is scenarios, not forecasts.")).toBeVisible();
    expect(within(note).getByText(/Every projection is labelled as such\./)).toBeVisible();
    expect(screen.getByText(/Those small caveats aren't clutter; they're the point\./)).toBeVisible();
    // The caveats, as the tags the reader will meet on the charts.
    const caveats = screen.getByRole("list", { name: "Caveats you will meet in the app" });
    expect(within(caveats).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Illustrative only",
      "Scenario, not a forecast",
      "Partial indicator coverage",
      "Low reliability",
    ]);
    expect(screen.getByText(/nothing here takes a political side/)).toBeVisible();
    expect(screen.getByText(/Conflict data, such as ACLED's, is not used\./)).toBeVisible();
    // English is final: no draft marker.
    expect(screen.queryByText(/Draft translation/)).not.toBeInTheDocument();
  });

  it("links to the views, the docs, the code and the maker", () => {
    render(<About />);
    const questions = screen.getByRole("heading", { name: "What you're looking at" }).closest("section");
    if (!questions) throw new Error("No views section");
    expect(within(questions).getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
      "/?view=past",
      "/?view=history",
      "/?view=counterfactual",
      "/?view=future",
    ]);
    expect(screen.getByRole("link", { name: "Methodology" })).toHaveAttribute(
      "href",
      "https://github.com/Zorrow14/project-amber/blob/main/docs/METHODOLOGY.md",
    );
    expect(screen.getByRole("link", { name: "Limitations" })).toHaveAttribute(
      "href",
      "https://github.com/Zorrow14/project-amber/blob/main/docs/LIMITATIONS.md",
    );
    expect(screen.getByRole("link", { name: "Source code (GitHub)" })).toHaveAttribute(
      "href",
      "https://github.com/Zorrow14/project-amber",
    );
    expect(screen.getByRole("link", { name: "About the maker" })).toHaveAttribute(
      "href",
      "https://htet-aung-lwin-portfolio.vercel.app",
    );
  });

  it("lists the sources by the role each plays, with the WDI licence", () => {
    render(<About />);
    const sources = screen.getByRole("region", { name: "Sources & citations" });
    for (const group of ["Data in the app", "Standards cited", "Cross-checks", "Scenario directions", "Methods", "Not used"]) {
      expect(within(sources).getByRole("heading", { name: group })).toBeVisible();
    }
    const wdi = within(sources).getByRole("link", { name: "World Bank, World Development Indicators (WDI)" });
    expect(wdi.closest("li")).toHaveTextContent("Licence: CC BY 4.0");
    const notUsed = within(sources).getByRole("region", { name: "Not used" });
    expect(within(notUsed).getByText(/ACLED/)).toBeVisible();
    expect(within(sources).getByRole("link", { name: /Synthetic Control Methods/ })).toHaveAttribute(
      "href",
      "https://doi.org/10.1198/jasa.2009.ap08746",
    );
  });

  it("says the same in Burmese, marking each honesty passage as a draft translation", () => {
    render(
      <InBurmese>
        <About />
      </InBurmese>,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Amber အကြောင်း" })).toBeVisible();
    const note = screen.getByRole("note");
    expect(within(note).getByText("မဖြစ်ခဲ့လျှင် ရလဒ်သည် ခန့်မှန်းတွက်ချက်မှုသာ ဖြစ်ပြီး အမှန်တရား မဟုတ်ပါ။")).toBeVisible();
    expect(within(note).getByText("အနာဂတ်သည် ဖြစ်နိုင်ခြေ အခြေအနေများသာ ဖြစ်ပြီး ကြိုတင်ဟောကိန်းများ မဟုတ်ပါ။")).toBeVisible();
    expect(screen.getByText("ဖြစ်နိုင်ခြေ အခြေအနေ၊ ကြိုတင်ဟောကိန်း မဟုတ်ပါ")).toBeVisible();
    expect(screen.getByText("သရုပ်ပြရန်သာ")).toBeVisible();
    // Not shipped as final: the honesty, neutrality and data passages each say they are a draft.
    expect(screen.getAllByText(/^မူကြမ်း ဘာသာပြန်/)).toHaveLength(3);
    expect(screen.queryByText(/crystal ball|not a forecast|estimate, not a fact/)).not.toBeInTheDocument();
    // Citations keep their published form, marked as English for screen readers.
    const wdi = screen.getByRole("link", { name: "World Bank, World Development Indicators (WDI)" });
    expect(wdi.closest("cite")).toHaveAttribute("lang", "en");
    expect(document.documentElement.lang).toBe("my");
  });
});

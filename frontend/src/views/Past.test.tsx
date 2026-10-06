import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { ApiError } from "../api/client";
import type { IndexResponse, Meta, PanelResponse } from "../api/types";
import { MetaContext } from "../context/metaContext";
import { RouteProvider } from "../context/route";
import { twin } from "../test/twin";
import { Past } from "./Past";

// Coverage must stay visible wherever the index is drawn - in the legend, the
// notes and the text alternative - and a rejected weighting must say why while
// keeping the last valid chart on screen.

const COVERAGE = "Pillars average over the indicators each country reports.";

const meta = {
  treatment_year: 2021,
  modeling_window: { start: 2011, end: 2024 },
  covid_years: [2020],
  countries: [
    { iso3: "MMR", name: "Myanmar", treated: true, donor: false },
    { iso3: "VNM", name: "Vietnam", treated: false, donor: true },
  ],
  pillars: [
    { id: "economy", label: "Economy", default_weight: 1 },
    { id: "human_development", label: "Human development", default_weight: 1 },
  ],
  indicators: [{ id: "NY.GDP.PCAP.KD", name: "GDP per capita", in_index: true }],
  sc_outcomes: [{ id: "NY.GDP.PCAP.KD", is_currency: true }],
  framing: { coverage: COVERAGE, fiscal_year: "Myanmar's WDI year runs October-September." },
} as unknown as Meta;

const index: IndexResponse = {
  method: "goalposts",
  weights: { economy: 0.5, human_development: 0.5 },
  computed_live: true,
  coverage_note: COVERAGE,
  coverage_note_i18n: twin(COVERAGE),
  rows: [
    { country_iso3: "MMR", country_name: "Myanmar", year: 2023, series: "combined", value: 0.5, coverage: 1 },
    { country_iso3: "MMR", country_name: "Myanmar", year: 2024, series: "combined", value: 0.52, coverage: 0.67 },
    { country_iso3: "VNM", country_name: "Vietnam", year: 2023, series: "combined", value: 0.7, coverage: 1 },
    { country_iso3: "VNM", country_name: "Vietnam", year: 2024, series: "combined", value: 0.71, coverage: 1 },
  ].map((row) => ({ ...row, country_name_i18n: twin(row.country_name) })),
};

const panel: PanelResponse = { indicators: [], countries: [], rows: [], coverage: [] };

const indexCall = vi.fn();
vi.mock("../api/client", async (original) => ({
  ...(await original<typeof import("../api/client")>()),
  api: { index: (...args: unknown[]) => indexCall(...args), panel: () => Promise.resolve(panel) },
}));

function renderPast() {
  return render(
    <MetaContext.Provider value={meta}>
      <Past />
    </MetaContext.Provider>,
  );
}

async function indexChart(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { name: /Combined development index/ });
  const figure = heading.closest("figure");
  if (!figure) throw new Error("The chart heading is not inside its figure");
  return figure;
}

afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
});

describe("Past", () => {
  it("keeps changed pillar weights in the URL, and starts from them", async () => {
    indexCall.mockResolvedValue(index);
    window.history.replaceState(null, "", "/?view=past&weights=economy:0.4");
    const first = render(
      <RouteProvider>
        <MetaContext.Provider value={meta}>
          <Past />
        </MetaContext.Provider>
      </RouteProvider>,
    );
    const [economy, human] = screen.getAllByRole("slider");
    expect(economy).toHaveValue("0.4");
    expect(human).toHaveValue("1"); // unnamed weights keep their default exactly
    await waitFor(() => expect(indexCall).toHaveBeenLastCalledWith({ economy: 0.4, human_development: 1 }, expect.anything()));

    if (!human) throw new Error("No slider for the second pillar");
    fireEvent.change(human, { target: { value: "0.25" } });
    await waitFor(() => expect(window.location.search).toBe("?view=past&weights=economy:0.4,human_development:0.25"));
    first.unmount();
  });

  it("downloads the loaded series as CSV, with the caveats and the source first", async () => {
    indexCall.mockResolvedValue(index);
    const files: Blob[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      files.push(blob as Blob);
      return "blob:amber";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderPast();
    const chart = await indexChart();
    await waitFor(() => expect(within(chart).getByText(/rests on 67%/, { selector: "li" })).toBeVisible());

    fireEvent.click(within(chart).getByRole("button", { name: "Download this chart's data as CSV" }));
    expect(await within(chart).findByText("Downloaded amber-development-index.csv")).toBeInTheDocument();
    const [file] = files;
    if (!file) throw new Error("No file was downloaded");
    const lines = (await file.text()).replace(/^\uFEFF/, "").split("\r\n");

    // The words around the chart travel with the data: coverage caveat, source, origin.
    expect(lines[0]).toMatch(/^# Combined development index/);
    expect(lines).toContain(`# ${COVERAGE}`);
    expect(lines).toContain("# Myanmar partial from 2024");
    expect(lines).toContain("# Source: World Bank, World Development Indicators; Amber's index.");
    expect(lines.some((line) => /^# Exported from Amber on \d{4}-\d{2}-\d{2}: http/.test(line))).toBe(true);
    // Then the loaded series, unformatted, with each country's coverage beside it.
    expect(lines).toContain("Year,Myanmar,Vietnam,Myanmar: indicator coverage,Vietnam: indicator coverage");
    expect(lines).toContain("2023,0.5,0.7,1,1");
    expect(lines).toContain("2024,0.52,0.71,0.67,1");
  });

  it("shows partial coverage in the legend, the notes and the data table", async () => {
    indexCall.mockResolvedValue(index);
    renderPast();
    const chart = await indexChart();

    await waitFor(() => expect(within(chart).getByText(/rests on 67% of its indicators/, { selector: "li" })).toBeVisible());
    expect(within(chart).getByText("Partial indicator coverage")).toBeVisible();
    expect(within(chart).getByText(COVERAGE)).toBeVisible();
    expect(within(chart).getByText("0.52 (partial, 67% of indicators)")).toBeInTheDocument();
    expect(within(chart).getByText(/Hollow points mark scores computed from partial/)).toBeInTheDocument();
  });

  it("explains a rejected weighting and keeps the last valid index on screen", async () => {
    indexCall.mockResolvedValueOnce(index);
    renderPast();
    const chart = await indexChart();
    await waitFor(() => expect(within(chart).getByText(/rests on 67%/, { selector: "li" })).toBeVisible());

    indexCall.mockRejectedValue(new ApiError(422, "Pillar weights sum to zero; give at least one pillar weight"));
    for (const slider of screen.getAllByRole("slider")) fireEvent.change(slider, { target: { value: "0" } });

    expect(await within(chart).findByText("These weights cannot produce an index")).toBeVisible();
    expect(within(chart).getByText(/sum to zero.*last result that loaded/)).toBeVisible();
    expect(within(chart).getByText("0.52 (partial, 67% of indicators)")).toBeInTheDocument();
    expect(indexCall).toHaveBeenCalledTimes(2); // a 422 is not retried
  });
});

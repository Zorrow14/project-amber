import { tableCsv } from "./export";

describe("the CSV export", () => {
  it("writes the frame's words as comments, then raw values, quoting only where needed", () => {
    const csv = tableCsv(
      {
        caption: "Donor weights",
        columns: ["Donor", "Weight"],
        rows: [
          ["Vietnam", "62.5%"],
          ["Lao PDR, \"Laos\"", "37.5%"],
        ],
        data: {
          columns: ["Donor", "Weight"],
          rows: [
            ["Vietnam", 0.625],
            ['Lao PDR, "Laos"', 0.375],
            ["Nepal", null],
          ],
        },
      },
      {
        title: "Who synthetic Myanmar is made of",
        subtitle: "",
        caveats: ["Illustrative only"],
        notes: ["A note\nover two lines."],
        source: "Source: World Bank, World Development Indicators.",
      },
      ["Exported from Amber on 2026-10-06: https://amber-sim.vercel.app/?view=counterfactual"],
    );

    expect(csv.charCodeAt(0)).toBe(0xfeff); // spreadsheets read the UTF-8 (Burmese labels) correctly
    expect(csv.slice(1).split("\r\n")).toEqual([
      "# Who synthetic Myanmar is made of",
      "# Illustrative only",
      "# A note over two lines.",
      "# Source: World Bank, World Development Indicators.",
      "# Exported from Amber on 2026-10-06: https://amber-sim.vercel.app/?view=counterfactual",
      "Donor,Weight",
      "Vietnam,0.625",
      '"Lao PDR, ""Laos""",0.375',
      "Nepal,",
      "",
    ]);
  });

  it("falls back to the cells as shown when a table has no raw values", () => {
    const csv = tableCsv(
      { caption: "", columns: ["Year", "Value"], rows: [["2024", "$1,158"]] },
      { title: "", subtitle: "", caveats: [], notes: [], source: "" },
      [],
    );
    expect(csv.slice(1)).toBe('Year,Value\r\n2024,"$1,158"\r\n');
  });
});

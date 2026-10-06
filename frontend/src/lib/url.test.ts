import { DEFAULT_VIEW, formatLocation, formatNumbers, parseLocation, parseNumbers, snap } from "./url";

// The URL is the app's shareable state: whatever a link holds must come back
// out of it unchanged, and anything malformed must fall back, never break.

describe("the URL schema", () => {
  it("lands on About when the URL names no view", () => {
    expect(DEFAULT_VIEW).toBe("about");
    expect(parseLocation("", "").view).toBe("about");
    expect(formatLocation({ view: "about" })).toBe("/");
  });

  it("round-trips a view's state, the language and foreign parameters", () => {
    const href = "/?view=future&scenario=reform_push&levers=education_spend:1.5,fdi_openness:0.8&series=Y&lang=my&utm_source=mail";
    const location = parseLocation(href.slice(1));
    expect(location).toEqual({
      view: "future",
      lang: "my",
      params: { scenario: "reform_push", levers: "education_spend:1.5,fdi_openness:0.8", series: "Y" },
      anchor: null,
      extra: [["utm_source", "mail"]],
    });
    expect(formatLocation(location)).toBe(href);
  });

  it("keeps only the open view's parameters", () => {
    const location = parseLocation("?view=past&weights=economy:0.5&levers=education_spend:2");
    expect(location.params).toEqual({ weights: "economy:0.5" });
    expect(formatLocation(location)).toBe("/?view=past&weights=economy:0.5");
  });

  it("still opens old hash links, and points at a section by its id", () => {
    expect(parseLocation("", "#/counterfactual").view).toBe("counterfactual");
    expect(parseLocation("?view=history", "#/past").view).toBe("history"); // the query wins
    expect(parseLocation("?view=about", "#sources")).toMatchObject({ view: "about", anchor: "sources" });
    expect(formatLocation({ view: "about", anchor: "sources" })).toBe("/#sources");
  });

  it("falls back on an unknown view or language", () => {
    expect(parseLocation("?view=admin&lang=fr")).toMatchObject({ view: DEFAULT_VIEW, lang: null });
  });
});

describe("number maps", () => {
  it("write only what is needed, readable in the address bar", () => {
    expect(formatNumbers({ economy: 0.5, innovation: 0.25 })).toBe("economy:0.5,innovation:0.25");
    expect(formatNumbers({ education_spend: 1.2500000001 })).toBe("education_spend:1.25");
  });

  it("drop malformed pairs rather than guess", () => {
    expect(parseNumbers("economy:0.5,broken,innovation:x,human_development:1")).toEqual({
      economy: 0.5,
      human_development: 1,
    });
    expect(parseNumbers(undefined)).toEqual({});
  });

  it("clamp a value to its range and step", () => {
    expect(snap(9, 0.5, 2, 0.05)).toBe(2);
    expect(snap(0.1, 0.5, 2, 0.05)).toBe(0.5);
    expect(snap(1.26, 0.5, 2, 0.05)).toBe(1.25);
    expect(snap(0.333, 0, 1, 0.01)).toBe(0.33);
  });
});

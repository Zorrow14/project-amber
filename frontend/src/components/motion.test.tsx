import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { REDUCED_MOTION_QUERY } from "../hooks/useReducedMotion";
import { formatSignedPercent } from "../lib/format";
import { drawProps } from "../lib/motion";
import { StatCallout } from "./StatCallout";

// The accessibility guard for the motion layer: under prefers-reduced-motion
// the final state renders at once - no count-up, no intermediate value, no
// chart animation - while with motion allowed the same component does animate.

function prefersReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query === REDUCED_MOTION_QUERY ? reduce : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const GAP = -0.263;
const FINAL = formatSignedPercent(GAP);
const BASELINE = formatSignedPercent(0);

function renderGap() {
  render(
    <StatCallout
      label="GDP per capita gap, 2024"
      value={FINAL}
      count={{ value: GAP, from: 0, format: formatSignedPercent }}
      detail="against synthetic Myanmar: an estimate, not a forecast"
    />,
  );
  return document.querySelector("[data-animated-number]");
}

describe("reduced motion", () => {
  it("renders the final state immediately, with no animated intermediate", () => {
    prefersReducedMotion(true);
    const shown = renderGap();

    expect(shown).toHaveTextContent(FINAL);
    expect(shown).not.toHaveTextContent(BASELINE);
    expect(screen.getByText("against synthetic Myanmar: an estimate, not a forecast")).toBeVisible();
    expect(drawProps({ enabled: false })).toEqual({ isAnimationActive: false });
  });

  it("does animate when motion is allowed - so the test above guards something real", () => {
    prefersReducedMotion(false);
    const shown = renderGap();

    // First paint is the baseline; requestAnimationFrame then carries it to the value.
    expect(shown).toHaveTextContent(BASELINE);
    expect(drawProps({ enabled: true }).isAnimationActive).toBe(true);
    // The final value is what assistive tech reads, from the first paint, either way.
    expect(screen.getByText(FINAL)).toHaveClass("sr-only");
  });
});

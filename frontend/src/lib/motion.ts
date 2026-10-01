import { useReducedMotion } from "../hooks/useReducedMotion";

/**
 * Motion tokens. Recharts and requestAnimationFrame take durations as numbers,
 * so they live here; the CSS durations are in styles/tokens.css. Every value
 * is skipped entirely under `prefers-reduced-motion: reduce`.
 *
 * The rules: motion answers what the data does (a line drawing its path, a band
 * widening into the future, a number arriving at its value) and never carries
 * meaning alone; no caveat waits for an animation to finish.
 */
export const MOTION = {
  /** A line drawing its path on first view. */
  draw: 900,
  /** A second series starts this far into the first one's draw. */
  follow: 0.6,
  /** A band revealing left to right (it reaches its own start part-way through). */
  band: 1300,
  /** A number counting to its value, or a chart re-tweening between states. */
  tween: 600,
  /** Scrubber playback: one year per step. */
  step: 500,
  /** Numbers and bars moving between scrubber years: well under a step, so each
   * year's value is reached fast and held - never shown mid-way beside that year's
   * label and range. CSS --duration-tween matches it. */
  stepTween: 240,
  ease: "ease-out",
} as const;

export interface Motion {
  /** False under reduced motion: render the final state, animate nothing. */
  enabled: boolean;
}

/** The reader's motion preference, for charts and tweens. */
export function useMotion(): Motion {
  return { enabled: !useReducedMotion() };
}

/**
 * Recharts animation props for one series: draw on first view and re-tween
 * between data states, or nothing at all under reduced motion.
 */
export function drawProps(
  motion: Motion,
  { begin = 0, duration = MOTION.draw }: { begin?: number; duration?: number } = {},
) {
  return motion.enabled
    ? {
        isAnimationActive: true,
        animationBegin: begin,
        animationDuration: duration,
        animationEasing: MOTION.ease,
      }
    : { isAnimationActive: false };
}

/**
 * One series split at its reliability boundary draws as one stroke: the low
 * segment first, the standard segment picking up where it ends, each for its
 * share of the years.
 */
export function segmentDraw(motion: Motion, years: number[], boundary: number | null, begin = 0) {
  const first = years.length > 0 ? Math.min(...years) : 0;
  const last = years.length > 0 ? Math.max(...years) : 0;
  const span = last - first;
  const share = boundary != null && span > 0 ? Math.min(1, Math.max(0, (boundary - first) / span)) : 0;
  return {
    low: drawProps(motion, { begin, duration: Math.max(1, MOTION.draw * share) }),
    standard: drawProps(motion, { begin: begin + MOTION.draw * share, duration: Math.max(1, MOTION.draw * (1 - share)) }),
  };
}

import { useEffect, useRef, useState } from "react";

import { MOTION } from "../lib/motion";
import { useReducedMotion } from "./useReducedMotion";

/**
 * A number that eases to `target` on requestAnimationFrame: from `from` on
 * first view, then from wherever it is to each new target. Under reduced motion
 * (or with no target) it is simply `target`, with no intermediate value ever
 * rendered.
 */
export function useTween(
  target: number | null,
  { from, duration = MOTION.tween }: { from?: number; duration?: number } = {},
): number | null {
  const reduced = useReducedMotion();
  const [value, setValue] = useState<number | null>(from ?? target);
  const shown = useRef<number | null>(from ?? target);

  useEffect(() => {
    if (reduced || target == null) {
      shown.current = target;
      return;
    }
    const start = shown.current ?? target;
    if (start === target) return;
    const t0 = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      const progress = Math.min(1, (now - t0) / duration);
      const eased = 1 - (1 - progress) ** 3;
      const next = start + (target - start) * eased;
      shown.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [target, reduced, duration]);

  if (reduced || target == null) return target;
  return value ?? target;
}

import { useEffect, useState } from "react";

import { MOTION } from "../lib/motion";

export interface Playback {
  /** The current step, clamped to the series. */
  index: number;
  playing: boolean;
  /** Whether the reader has moved away from the final step (or is playing). */
  scrubbed: boolean;
  /** Start playing - from the beginning if already at the end. */
  play: () => void;
  pause: () => void;
  toggle: () => void;
  /** Jump to a step; pauses playback, since the reader has taken over. */
  seek: (index: number) => void;
}

/**
 * The scrubber's state: one index into a series of years, and whether it is
 * playing. It starts at the final step, so the static view is the final state
 * and nothing moves until the reader presses play. Playback advances one step
 * every `stepMs` and stops at the end; it never starts on its own.
 */
export function usePlayback(length: number, stepMs: number = MOTION.step): Playback {
  const last = Math.max(0, length - 1);
  const [raw, setRaw] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const index = raw == null ? last : Math.min(raw, last);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      const next = Math.min(index + 1, last);
      setRaw(next);
      if (next >= last) setPlaying(false);
    }, stepMs);
    return () => window.clearTimeout(timer);
  }, [playing, index, last, stepMs]);

  const play = () => {
    if (index >= last) setRaw(0);
    setPlaying(last > 0);
  };
  const pause = () => setPlaying(false);
  return {
    index,
    playing,
    scrubbed: playing || index < last,
    play,
    pause,
    toggle: () => (playing ? pause() : play()),
    seek: (next) => {
      setPlaying(false);
      setRaw(Math.max(0, Math.min(next, last)));
    },
  };
}

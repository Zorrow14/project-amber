import type { Playback } from "../hooks/usePlayback";
import { Icon } from "./Icon";

/**
 * Play and scrub through a series of years. A native range input, so it works
 * with arrow keys, Home/End and touch; the play button says what it will do.
 * The year readout is announced only when the reader stops on a year, never on
 * every step of playback.
 */
export function TimeScrubber({
  years,
  playback,
  label,
}: {
  years: number[];
  playback: Playback;
  label: string;
}) {
  const year = years[playback.index];
  const first = years[0];
  return (
    <div className="scrubber">
      <button
        type="button"
        className="button scrubber__play"
        onClick={playback.toggle}
        aria-pressed={playback.playing}
        disabled={years.length < 2}
      >
        <Icon name={playback.playing ? "pause" : "play"} />
        <span>{playback.playing ? "Pause" : `Play from ${first ?? ""}`}</span>
      </button>
      <input
        className="scrubber__track"
        type="range"
        min={0}
        max={Math.max(0, years.length - 1)}
        step={1}
        value={playback.index}
        onChange={(event) => playback.seek(Number(event.target.value))}
        aria-label={label}
        aria-valuetext={year != null ? String(year) : undefined}
      />
      <output className="scrubber__year num" aria-live={playback.playing ? "off" : "polite"}>
        {year ?? "–"}
      </output>
    </div>
  );
}

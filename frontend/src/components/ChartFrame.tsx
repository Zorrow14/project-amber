import { useId, type ReactNode } from "react";

import { Pill, type PillTone } from "./Banner";
import { DataTable, type TableSpec } from "./DataTable";

/**
 * The frame every chart sits in, so they all read alike: title and claim; the
 * caveat pill and any honesty callout in one fixed place above the plot; the
 * plot; then notes, source and the data table.
 *
 * `badge` is a caveat ("Illustrative only", "Scenario, not a forecast") and is
 * always shown; `status` is transient ("Updating…") and sits beside it, never in
 * its place. `summary` is read to screen readers in place of the plot, and
 * `table` offers every value behind it.
 */
export function ChartFrame({
  title,
  subtitle,
  badge,
  badgeTone = "critical",
  status,
  callout,
  legend,
  seriesLegend,
  notes,
  source,
  summary,
  table,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  badge?: string;
  badgeTone?: PillTone;
  status?: string;
  /** The honesty slot: a coverage pill or a short caveat, rendered above the plot. */
  callout?: ReactNode;
  /** Keys that always show (line styles, the hollow coverage ring). */
  legend?: ReactNode;
  /** A per-series legend for phone width, where direct end labels do not fit. */
  seriesLegend?: ReactNode;
  notes?: ReactNode[];
  source?: string;
  summary: string;
  table?: TableSpec | null;
  children: ReactNode;
}) {
  const summaryId = useId();
  return (
    <figure className="chart-frame" aria-describedby={summaryId}>
      <figcaption className="chart-frame__head">
        <div className="chart-frame__titles">
          <h3 className="chart-frame__title">{title}</h3>
          {subtitle ? <p className="chart-frame__subtitle">{subtitle}</p> : null}
        </div>
        <div className="chart-frame__pills">
          {badge ? (
            <Pill tone={badgeTone} data-caveat>
              {badge}
            </Pill>
          ) : null}
          <Pill tone="status" role="status" data-status hidden={!status}>
            {status}
          </Pill>
        </div>
      </figcaption>
      <p className="sr-only" id={summaryId}>
        {summary}
      </p>
      {callout ? <div className="chart-frame__callout">{callout}</div> : null}
      {legend || seriesLegend ? (
        <div className="stack">
          {seriesLegend ? <div className="legend legend--narrow-only">{seriesLegend}</div> : null}
          {legend ? <div className="legend">{legend}</div> : null}
        </div>
      ) : null}
      <div className="chart-frame__plot">{children}</div>
      {(notes && notes.length > 0) || source || table ? (
        <footer className="chart-frame__foot">
          {notes && notes.length > 0 ? (
            <ul className="chart-frame__notes">
              {notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          ) : null}
          {source ? <p className="chart-frame__source">{source}</p> : null}
          {table ? <DataTable spec={table} /> : null}
        </footer>
      ) : null}
    </figure>
  );
}

export function LegendItem({
  color,
  label,
  variant = "line",
}: {
  color: string;
  label: string;
  variant?: "line" | "dashed" | "dotted" | "band" | "hollow" | "bold" | "hatch" | "bracket";
}) {
  return (
    <span className="legend__item">
      <span className={`legend__swatch legend__swatch--${variant}`} style={{ color }} aria-hidden />
      {label}
    </span>
  );
}

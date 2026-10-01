import { useId, type ReactNode } from "react";

import { DataTable, type TableSpec } from "./DataTable";

/**
 * A chart with its title, the claim it supports, its caveats underneath, and a
 * text alternative: `summary` is read to screen readers in place of the plot,
 * and `table` offers every value behind it.
 *
 * `badge` is a caveat ("Illustrative only") and is always shown; `status` is
 * transient ("Updating…") and sits beside it, never in its place.
 */
export function ChartCard({
  title,
  subtitle,
  badge,
  status,
  notes,
  legend,
  summary,
  table,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  badge?: string;
  status?: string;
  notes?: ReactNode[];
  legend?: ReactNode;
  summary: string;
  table?: TableSpec | null;
  children: ReactNode;
}) {
  const summaryId = useId();
  return (
    <figure className="card chart-card" aria-describedby={summaryId}>
      <figcaption className="chart-card__head">
        <div className="chart-card__title-row">
          <h3>{title}</h3>
          {badge ? <span className="badge badge--caveat">{badge}</span> : null}
          <span className="badge badge--status" role="status" hidden={!status}>
            {status}
          </span>
        </div>
        {subtitle ? <p className="chart-card__subtitle">{subtitle}</p> : null}
      </figcaption>
      <p className="sr-only" id={summaryId}>
        {summary}
      </p>
      {legend ? <div className="legend">{legend}</div> : null}
      <div className="chart-card__plot">{children}</div>
      {notes && notes.length > 0 ? (
        <ul className="chart-card__notes">
          {notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      ) : null}
      {table ? <DataTable spec={table} /> : null}
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
  variant?: "line" | "dashed" | "dotted" | "band" | "hollow" | "bold";
}) {
  return (
    <span className="legend__item">
      <span className={`legend__swatch legend__swatch--${variant}`} style={{ color }} aria-hidden />
      {label}
    </span>
  );
}

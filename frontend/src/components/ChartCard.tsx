import type { ReactNode } from "react";

/** A chart with its title, the claim it supports, and its caveats underneath. */
export function ChartCard({
  title,
  subtitle,
  badge,
  notes,
  legend,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  badge?: string;
  notes?: ReactNode[];
  legend?: ReactNode;
  children: ReactNode;
}) {
  return (
    <figure className="card chart-card">
      <figcaption className="chart-card__head">
        <div className="chart-card__title-row">
          <h3>{title}</h3>
          {badge ? <span className="badge">{badge}</span> : null}
        </div>
        {subtitle ? <p className="chart-card__subtitle">{subtitle}</p> : null}
      </figcaption>
      {legend ? <div className="legend">{legend}</div> : null}
      <div className="chart-card__plot">{children}</div>
      {notes && notes.length > 0 ? (
        <ul className="chart-card__notes">
          {notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
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
  variant?: "line" | "dashed" | "band" | "hollow" | "bold";
}) {
  return (
    <span className="legend__item">
      <span className={`legend__swatch legend__swatch--${variant}`} style={{ color }} aria-hidden />
      {label}
    </span>
  );
}

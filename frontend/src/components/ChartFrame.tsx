import { useId, useRef, useState, type ReactNode, type RefObject } from "react";

import { Link } from "../context/route";
import { useI18n } from "../i18n/context";
import { SOURCES_ANCHOR } from "../lib/url";
import { Pill, type PillTone } from "./Banner";
import { DataTable, type TableSpec } from "./DataTable";
import { Icon } from "./Icon";

/**
 * The frame every chart sits in, so they all read alike: title and claim; the
 * caveat pill and any honesty callout in one fixed place above the plot; the
 * plot; then notes, source and the data table.
 *
 * `badge` is a caveat ("Illustrative only", "Scenario, not a forecast") and is
 * always shown; `status` is transient ("Updating…") and sits beside it, never in
 * its place. `summary` is read to screen readers in place of the plot, and
 * `table` offers every value behind it.
 *
 * The foot also offers the chart's data as CSV and the chart as PNG; both
 * files carry the caveat, notes and source. `exportName` names them.
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
  exportName = "chart",
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
  /** The downloads' file name, without `amber-` or an extension: a stable ASCII slug. */
  exportName?: string;
  children: ReactNode;
}) {
  const summaryId = useId();
  const figure = useRef<HTMLElement>(null);
  return (
    <figure className="chart-frame" aria-describedby={summaryId} ref={figure}>
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
        <ExportActions figure={figure} table={table ?? null} name={exportName} />
      </footer>
    </figure>
  );
}

/**
 * Download the data (CSV) or the chart (PNG), and a link to where the data comes
 * from. The export code loads on first use; its result is announced.
 */
function ExportActions({
  figure,
  table,
  name,
}: {
  figure: RefObject<HTMLElement | null>;
  table: TableSpec | null;
  name: string;
}) {
  const { t } = useI18n();
  const [status, setStatus] = useState("");
  const run = async (kind: "csv" | "png") => {
    const node = figure.current;
    if (!node) return;
    const file = `amber-${name}.${kind}`;
    const footer = [
      t("export.exported", { date: new Date().toISOString().slice(0, 10), url: window.location.href }),
      t("export.licence"),
    ];
    try {
      const exporter = await import("../lib/export");
      if (kind === "csv" && table) exporter.exportCsv(node, table, footer, file);
      else if (!(await exporter.exportPng(node, footer, file))) {
        setStatus(t("export.notReady"));
        return;
      }
      setStatus(t("export.done", { file }));
    } catch {
      setStatus(t("export.failed"));
    }
  };
  return (
    <div className="chart-frame__actions">
      {table ? (
        <button
          type="button"
          className="button"
          onClick={() => run("csv")}
          aria-label={t("export.csvLabel")}
          title={t("export.csvLabel")}
        >
          <Icon name="download" />
          {t("export.csv")}
        </button>
      ) : null}
      <button
        type="button"
        className="button"
        onClick={() => run("png")}
        aria-label={t("export.pngLabel")}
        title={t("export.pngLabel")}
      >
        <Icon name="download" />
        {t("export.png")}
      </button>
      <Link view="about" anchor={SOURCES_ANCHOR} className="chart-frame__sources">
        {t("sources.link")}
      </Link>
      <span className="chart-frame__export-status" role="status">
        {status}
      </span>
    </div>
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

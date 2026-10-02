/**
 * Text alternatives for the charts: a one-paragraph summary for screen readers
 * and a table of every value. Both are built from the same rows the chart
 * draws, so they cannot drift from it - and they carry the same caveats, in the
 * UI language.
 */
import type { TableSpec } from "../components/DataTable";
import type { I18n } from "../i18n/context";

type Row = Record<string, number | null | undefined>;
type Format = (value: number) => string;

export interface SeriesKey {
  key: string;
  label: string;
}

function cell(value: number | null | undefined, format: Format): string {
  return value == null || !Number.isFinite(value) ? "–" : format(value);
}

/** Year-by-series table. `coverageKey(key)` names a coverage column; < 1 is marked partial. */
export function seriesTable(
  i18n: I18n,
  caption: string,
  rows: Row[],
  series: SeriesKey[],
  format: Format,
  coverageKey?: (key: string) => string,
): TableSpec {
  return {
    caption,
    columns: [i18n.t("charts.year"), ...series.map((s) => s.label)],
    rows: rows.map((row) => [
      String(row.year),
      ...series.map((s) => {
        const text = cell(row[s.key], format);
        const coverage = coverageKey ? row[coverageKey(s.key)] : undefined;
        return typeof coverage === "number" && coverage < 1 && text !== "–"
          ? i18n.t("charts.partialCell", { value: text, share: `${Math.round(coverage * 100)}%` })
          : text;
      }),
    ]),
  };
}

/** First and last year with a value for `key`, and those values. */
export function endpoints(rows: Row[], key: string): { first?: [number, number]; last?: [number, number] } {
  const points = rows
    .map((r) => [Number(r.year), r[key]] as const)
    .filter((p): p is readonly [number, number] => p[1] != null && Number.isFinite(p[1]));
  const first = points[0];
  const last = points.at(-1);
  return { first: first ? [first[0], first[1]] : undefined, last: last ? [last[0], last[1]] : undefined };
}

/**
 * "Line chart of X, 2011–2024, one line per country. Myanmar: a in 2011, b in 2024.
 * In 2024 the highest is ..., the lowest ..."
 */
export function describeCountryLines(
  i18n: I18n,
  what: string,
  rows: Row[],
  countries: { iso3: string; name: string; treated: boolean }[],
  format: Format,
): string {
  const { t } = i18n;
  if (rows.length === 0) return t("charts.noData", { what });
  const years = rows.map((r) => Number(r.year));
  const parts = [t("charts.lineChart", { what, from: Math.min(...years), to: Math.max(...years) })];
  const treated = countries.find((c) => c.treated);
  if (treated) {
    const { first, last } = endpoints(rows, treated.iso3);
    if (first && last) {
      parts.push(
        t("charts.endpoints", {
          country: treated.name,
          first: format(first[1]),
          firstYear: first[0],
          last: format(last[1]),
          lastYear: last[0],
        }),
      );
    }
  }
  const lastRow = [...rows].reverse().find((r) => countries.some((c) => r[c.iso3] != null));
  if (lastRow) {
    const ranked = countries
      .filter((c) => lastRow[c.iso3] != null)
      .sort((a, b) => Number(lastRow[b.iso3]) - Number(lastRow[a.iso3]));
    const top = ranked[0];
    const bottom = ranked.at(-1);
    if (top && bottom && top !== bottom) {
      parts.push(
        t("charts.extremes", {
          year: Number(lastRow.year),
          top: top.name,
          topValue: format(Number(lastRow[top.iso3])),
          bottom: bottom.name,
          bottomValue: format(Number(lastRow[bottom.iso3])),
        }),
      );
    }
  }
  return parts.join(" ");
}

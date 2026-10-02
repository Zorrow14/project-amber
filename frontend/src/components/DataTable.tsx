import { useId } from "react";

import { useT } from "../i18n/context";

/** A chart's data as rows - its text alternative, and a way to read exact values. */
export interface TableSpec {
  caption: string;
  columns: string[];
  /** One row per entry; the first cell labels the row (usually the year). */
  rows: string[][];
}

/** A collapsed "view as table" disclosure; the table scrolls sideways on narrow screens. */
export function DataTable({ spec }: { spec: TableSpec }) {
  const id = useId();
  const t = useT();
  return (
    <details className="data-table">
      <summary>{t("controls.viewTable")}</summary>
      <div className="data-table__scroll" role="region" aria-labelledby={id} tabIndex={0}>
        <table>
          <caption id={id}>{spec.caption}</caption>
          <thead>
            <tr>
              {spec.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {spec.rows.map((row, i) => (
              <tr key={row[0] ?? i}>
                {row.map((cell, j) =>
                  j === 0 ? (
                    <th key={j} scope="row">
                      {cell}
                    </th>
                  ) : (
                    <td key={j}>{cell}</td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/**
 * The one tooltip card every chart uses: the year as a title, then one row per
 * series - swatch, name, right-aligned tabular value - sorted high to low, with
 * an optional per-row note (e.g. partial coverage).
 */

interface Row {
  name?: unknown;
  value?: unknown;
  color?: string;
  stroke?: string;
  fill?: string;
  dataKey?: unknown;
  payload?: Record<string, unknown>;
}

export interface TooltipOptions {
  format: (value: number) => string;
  /** A note under a row, e.g. "partial: 67% of indicators". */
  note?: (row: { dataKey: string; payload: Record<string, unknown> }) => string | null;
  /** Keep the chart's own series order instead of sorting by value. */
  keepOrder?: boolean;
}

function numeric(value: unknown): number | null {
  if (Array.isArray(value)) return null;
  const n = Number(value);
  return value == null || !Number.isFinite(n) ? null : n;
}

export function ChartTooltip({
  active,
  payload,
  label,
  format,
  note,
  keepOrder = false,
}: {
  active?: boolean;
  payload?: readonly unknown[];
  label?: unknown;
} & TooltipOptions) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = (payload as Row[]).filter((row) => row.value != null);
  if (!keepOrder) {
    rows.sort((a, b) => (numeric(b.value) ?? -Infinity) - (numeric(a.value) ?? -Infinity));
  }
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title num">{String(label)}</div>
      <div className="chart-tooltip__rows">
        {rows.map((row) => {
          const value = Array.isArray(row.value)
            ? `${format(Number(row.value[0]))} – ${format(Number(row.value[1]))}`
            : format(Number(row.value));
          const extra = note && row.payload ? note({ dataKey: String(row.dataKey), payload: row.payload }) : null;
          return (
            <div key={String(row.dataKey)} className="chart-tooltip__row">
              <span className="chart-tooltip__swatch" style={{ background: row.color ?? row.stroke ?? row.fill }} />
              <span className="chart-tooltip__name">{String(row.name)}</span>
              <span className="chart-tooltip__value">{value}</span>
              {extra ? <span className="chart-tooltip__note">{extra}</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

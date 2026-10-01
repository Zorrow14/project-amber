/** Pivot tidy rows into Recharts' one-object-per-x form. */
export function pivot<R>(
  rows: R[],
  x: (row: R) => number,
  key: (row: R) => string,
  value: (row: R) => number | null,
  extra?: (row: R) => Record<string, number | null>,
): Record<string, number | null>[] {
  const byX = new Map<number, Record<string, number | null>>();
  for (const row of rows) {
    const at = x(row);
    const entry = byX.get(at) ?? { year: at };
    entry[key(row)] = value(row);
    if (extra) Object.assign(entry, extra(row));
    byX.set(at, entry);
  }
  return [...byX.values()].sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
}

/** Index of the last entry where `key` has a value - where its end label goes. */
export function lastIndexWith(data: Record<string, number | null>[], key: string): number {
  for (let i = data.length - 1; i >= 0; i -= 1) {
    if (data[i]?.[key] != null) return i;
  }
  return -1;
}

/** The last non-null point of `key` in `rows`, as [x, y]. */
export function lastPoint(rows: Record<string, unknown>[], key: string, xKey = "year"): [number, number] | null {
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    const y = row?.[key];
    if (typeof y === "number" && Number.isFinite(y)) return [Number(row?.[xKey]), y];
  }
  return null;
}

/**
 * Split one series at its reliability boundary: `<key>` holds the standard
 * years, `<key>__low` the low ones plus the first standard year, so the two
 * segments meet. Returns the boundary year (first standard after a low run).
 */
export function splitByReliability<R extends { year: number; value: number | null; reliability: string }>(
  rows: R[],
  key: string,
  into: Map<number, Record<string, number | null>>,
): number | null {
  let boundary: number | null = null;
  let previousLow = false;
  for (const row of [...rows].sort((a, b) => a.year - b.year)) {
    const target = into.get(row.year) ?? { year: row.year };
    if (row.reliability === "low") {
      target[`${key}__low`] = row.value;
      previousLow = true;
    } else {
      target[key] = row.value;
      if (previousLow) {
        target[`${key}__low`] = row.value;
        boundary ??= row.year;
      }
      previousLow = false;
    }
    into.set(row.year, target);
  }
  return boundary;
}

/** A padded log domain over every numeric value of `keys` in `rows`. */
export function logDomain(rows: Record<string, unknown>[], keys: string[], pad: { below: number; above: number }): [number, number] | undefined {
  const values = rows.flatMap((row) => keys.map((key) => row[key])).filter((v): v is number => typeof v === "number" && v > 0);
  if (values.length === 0) return undefined;
  return [Math.min(...values) / pad.below, Math.max(...values) * pad.above];
}

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

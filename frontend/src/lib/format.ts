const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatDollars(value: number | null | undefined): string {
  return value == null ? "–" : dollars.format(value);
}

export function formatSignedDollars(value: number | null | undefined): string {
  if (value == null) return "–";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${dollars.format(Math.abs(value))}`;
}

export function formatIndex(value: number | null | undefined, digits = 3): string {
  return value == null ? "–" : value.toFixed(digits);
}

export function formatSignedIndex(value: number | null | undefined, digits = 3): string {
  if (value == null) return "–";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}`;
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  return value == null ? "–" : `${(value * 100).toFixed(digits)}%`;
}

export function formatSignedPercent(value: number | null | undefined, digits = 0): string {
  if (value == null) return "–";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value * 100).toFixed(digits)}%`;
}

/** Formatter for a value on a given outcome: dollars or index points. */
export function valueFormatter(isCurrency: boolean): (v: number | null | undefined) => string {
  return isCurrency ? formatDollars : (v) => formatIndex(v);
}

export function signedFormatter(isCurrency: boolean): (v: number | null | undefined) => string {
  return isCurrency ? formatSignedDollars : (v) => formatSignedIndex(v);
}

/** "Scenarios, not forecasts: each shows..." under that title reads "Each shows...". */
export function withoutLeadingTitle(text: string, title: string): string {
  if (!text.toLowerCase().startsWith(`${title.toLowerCase()}:`)) return text;
  const rest = text.slice(title.length + 1).trim();
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** An id as a file-name slug: "NY.GDP.PCAP.KD" -> "ny-gdp-pcap-kd". */
export function slug(id: string): string {
  return id
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

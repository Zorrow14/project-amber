import { useState } from "react";

import { api } from "../api/client";
import type { DivergenceResponse, HistoricalResponse, Meta } from "../api/types";
import { Banner, Pill } from "../components/Banner";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { ControlPanel } from "../components/ControlPanel";
import type { TableSpec } from "../components/DataTable";
import { Async } from "../components/LoadState";
import { SectionHeader } from "../components/SectionHeader";
import { StatCallout, StatRow } from "../components/StatCallout";
import { DivergenceChart } from "../charts/DivergenceChart";
import { HistoricalChart, type HistoricalSeries } from "../charts/HistoricalChart";
import { useMeta } from "../context/metaContext";
import { useApi, type ApiState } from "../hooks/useApi";
import { usePlayback } from "../hooks/usePlayback";
import { TimeScrubber } from "../components/TimeScrubber";
import { CHART } from "../lib/chartTokens";
import { formatDollars, formatPercent, withoutLeadingTitle } from "../lib/format";
import { splitByReliability } from "../lib/shape";
import { useChartTheme } from "../lib/theme";

/** The divergence banner's title. Its body is the API's own framing, so the two cannot drift. */
const ILLUSTRATIVE_TITLE = "Illustrative scenario, not a causal estimate";

const ratio = (value: number) => `${value.toFixed(2)}×`;

/** The historical arc: the 1960+ reconstruction, then the illustrative long-run divergence. */
export function History() {
  const meta = useMeta();
  const historical = meta.historical;
  const [comparator, setComparator] = useState(historical.default_comparator);
  const series = useApi((signal) => api.historical({}, signal), "historical");
  const divergence = useApi((signal) => api.divergence(comparator, signal), `divergence:${comparator}`);
  const treated = historical.countries.find((c) => c.role === "treated")?.name ?? "Myanmar";

  return (
    <div className="view">
      <SectionHeader
        eyebrow="Historical arc"
        title={`How ${treated} got here, ${historical.window.start}–${historical.window.end}`}
        description={`Descriptive history from the first year the World Bank publishes, on one ruler. Nothing here is fitted: the combined index, the counterfactual and the scenarios stay in their ${meta.modeling_window.start}+ modeling window.`}
      />

      <Reconstruction meta={meta} state={series} />

      <section className="section" aria-labelledby="divergence-title">
        <SectionHeader
          level={2}
          id="divergence-title"
          title="How far the paths diverged"
          description={`An illustration with stated assumptions: ${treated}'s actual ${historical.divergence_anchor} level, grown at a comparator's actual growth rates.`}
        />
        <DivergencePanel meta={meta} state={divergence} comparator={comparator} onComparator={setComparator} />
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Shared
// --------------------------------------------------------------------------- //

function lowReliabilityRule(meta: Meta) {
  const treated = meta.historical.countries.find((c) => c.role === "treated");
  const rule = meta.historical.reliability.find((r) => r.country_iso3 === treated?.iso3);
  return { name: treated?.name ?? "Myanmar", until: rule?.standard_from ?? null };
}

/** The two honesty cues' legend keys - shown at every width, named so neither rests on color. */
function honestyKeys(meta: Meta, color: { hero: string; hatch: string; neutral: string }) {
  const { name, until } = lowReliabilityRule(meta);
  return (
    <>
      {until != null ? (
        <>
          <LegendItem color={color.hero} label={`${name} before ${until}: low reliability (dotted)`} variant="dotted" />
          <LegendItem color={color.hatch} label={`Hatched: low-reliability years`} variant="hatch" />
        </>
      ) : null}
      <LegendItem
        color={color.neutral}
        label={`Modeling window (${meta.modeling_window.start}+): scope, not data quality`}
        variant="bracket"
      />
    </>
  );
}

// --------------------------------------------------------------------------- //
// Reconstruction
// --------------------------------------------------------------------------- //

function Reconstruction({ meta, state }: { meta: Meta; state: ApiState<HistoricalResponse> }) {
  const theme = useChartTheme();
  const historical = meta.historical;
  const names = new Map(historical.countries.map((c) => [c.iso3, c.name]));
  const spine = historical.indicators.find(
    (i) => i.source === "wb_constant" && historical.default_indicators.includes(i.id),
  );
  const { name: treatedName, until } = lowReliabilityRule(meta);
  const treated = historical.countries.find((c) => c.role === "treated")?.iso3 ?? "";
  const countries = state.data?.countries ?? historical.default_countries;
  const comparators = countries.filter((c) => c !== treated).map((c) => names.get(c) ?? c);

  const wdi = state.data?.rows.filter((r) => r.source === "wb_constant" && r.indicator_id === spine?.id) ?? [];
  const maddison = state.data?.rows.filter((r) => r.source === "maddison") ?? [];
  const byYear = new Map<number, Record<string, number | null>>();
  let lowFrom: number | null = null;
  let lowUntil: number | null = null;
  for (const iso3 of countries) {
    const rows = wdi.filter((r) => r.country_iso3 === iso3);
    const boundary = splitByReliability(rows, iso3, byYear);
    const lows = rows.filter((r) => r.reliability === "low").map((r) => r.year);
    if (lows.length > 0) {
      lowFrom = Math.min(lowFrom ?? Infinity, ...lows);
      lowUntil = boundary ?? lowUntil;
    }
  }
  const data = [...byYear.values()].sort((a, b) => Number(a.year) - Number(b.year));
  const series: HistoricalSeries[] = countries.map((iso3) => ({
    key: iso3,
    label: names.get(iso3) ?? iso3,
    hero: iso3 === treated,
  }));
  const events = state.data?.events ?? historical.events;
  const notes = [
    ...(state.data?.notes ?? [historical.framing.low_reliability, historical.framing.modeling_window, historical.framing.rulers]),
    `Markers: ${events.map((e) => e.label).join(" · ")}.`,
  ];
  const first = data[0]?.year;
  const last = data.at(-1)?.year;
  const title = `${spine?.name.replace(/ \(.*\)$/, "") ?? "GDP per capita"}, ${first ?? historical.window.start}–${last ?? historical.window.end}`;
  const treatedValue = (row: Record<string, number | null>) => row[treated] ?? row[`${treated}__low`] ?? null;
  const firstRow = data.find((row) => treatedValue(row) != null);
  const lastRow = [...data].reverse().find((row) => treatedValue(row) != null);

  return (
    <section className="section" aria-labelledby="reconstruction-title">
      <ChartFrame
        title={title}
        subtitle={`${treatedName} and ${comparators.join(", ")} on one ruler: ${spine?.units ?? "constant 2015 US$"}, log scale, so equal slopes are equal growth. Hatched years are low reliability; the bracket marks the modeling window.`}
        callout={until != null ? <Pill tone="caution">{`${treatedName} before ${until}: low reliability`}</Pill> : null}
        status={state.loading && state.data ? "Updating…" : undefined}
        seriesLegend={series.map((s) => (
          <LegendItem key={s.key} color={s.hero ? theme.hero : theme.neutral} label={s.label} variant={s.hero ? "bold" : "line"} />
        ))}
        legend={honestyKeys(meta, theme)}
        notes={notes}
        source="Source: World Bank, World Development Indicators (constant 2015 US$)."
        summary={[
          `Line chart of ${spine?.name ?? "GDP per capita"} on a log scale, ${first ?? "–"}–${last ?? "–"}, for ${series.map((s) => s.label).join(" and ")}.`,
          firstRow && lastRow
            ? `${treatedName}: ${formatDollars(treatedValue(firstRow))} in ${firstRow.year}, ${formatDollars(treatedValue(lastRow))} in ${lastRow.year}.`
            : "",
          until != null ? `${treatedName}'s values before ${until} are low reliability, drawn dotted over hatching.` : "",
          `A bracket marks the modeling window from ${meta.modeling_window.start}.`,
          `Markers: ${events.map((e) => e.label).join(", ")}.`,
        ]
          .filter(Boolean)
          .join(" ")}
        table={data.length > 0 ? historicalTable(title, data, series, treated) : null}
      >
        <Async state={state} what="the historical series" height={CHART.height} isEmpty={(d) => d.rows.length === 0}>
          {() => (
            <HistoricalChart
              data={data}
              series={series}
              events={events}
              lowFrom={lowFrom}
              lowUntil={lowUntil}
              windowStart={meta.modeling_window.start}
              format={formatDollars}
            />
          )}
        </Async>
      </ChartFrame>

      {maddison.length > 0 ? <MaddisonFrame meta={meta} rows={maddison} /> : null}
    </section>
  );
}

function historicalTable(
  caption: string,
  data: Record<string, number | null>[],
  series: HistoricalSeries[],
  treated: string,
): TableSpec {
  return {
    caption: `${caption}, by year and country`,
    columns: ["Year", ...series.map((s) => s.label)],
    rows: data.map((row) => [
      String(row.year),
      ...series.map((s) => {
        const standard = row[s.key];
        const low = row[`${s.key}__low`];
        if (standard != null) return formatDollars(standard);
        if (low != null) return `${formatDollars(low)}${s.key === treated ? " (low reliability)" : ""}`;
        return "–";
      }),
    ]),
  };
}

/** The pre-1960 Maddison series - only when the snapshot holds it, on its own axis and ruler. */
function MaddisonFrame({ meta, rows }: { meta: Meta; rows: HistoricalResponse["rows"] }) {
  const theme = useChartTheme();
  const indicator = meta.historical.indicators.find((i) => i.source === "maddison");
  const byYear = new Map<number, Record<string, number | null>>();
  const iso3 = rows[0]?.country_iso3 ?? "";
  splitByReliability(rows, iso3, byYear);
  const data = [...byYear.values()].sort((a, b) => Number(a.year) - Number(b.year));
  const name = meta.historical.countries.find((c) => c.iso3 === iso3)?.name ?? iso3;
  const years = rows.map((r) => r.year);
  const lows = rows.filter((r) => r.reliability === "low").map((r) => r.year);
  const units = indicator?.units ?? "2011 int$, PPP";
  return (
    <ChartFrame
      title={`Before ${meta.historical.window.start}: ${name}, Maddison Project`}
      subtitle={`A different ruler: GDP per capita in ${units}. Not comparable with the constant-US$ line above, so it is never joined to it.`}
      badge={`Different units (${units})`}
      badgeTone="neutral"
      legend={<LegendItem color={theme.hatch} label="Hatched: low-reliability years" variant="hatch" />}
      notes={[meta.historical.framing.maddison, meta.historical.framing.low_reliability]}
      source="Source: Maddison Project Database 2023 (Bolt and van Zanden 2024), CC BY 4.0."
      summary={`Line chart of ${name}'s GDP per capita in ${units}, ${Math.min(...years)}–${Math.max(...years)}, from the Maddison Project. A different ruler from the World Bank series; every value is low reliability.`}
      table={{
        caption: `${name}, GDP per capita (${units}), Maddison Project`,
        columns: ["Year", `${name} (${units})`, "Reliability"],
        rows: rows.map((r) => [String(r.year), formatDollars(r.value), r.reliability]),
      }}
    >
      <HistoricalChart
        data={data}
        series={[{ key: iso3, label: name, hero: true }]}
        events={[]}
        lowFrom={lows.length > 0 ? Math.min(...lows) : null}
        lowUntil={lows.length > 0 ? Math.max(...lows) : null}
        windowStart={meta.modeling_window.start}
        format={formatDollars}
      />
    </ChartFrame>
  );
}

// --------------------------------------------------------------------------- //
// Divergence
// --------------------------------------------------------------------------- //

/**
 * The long-run divergence: the illustrative banner (always shown, loading or
 * loaded), the comparator, the headline ratio and the chart. Exported for the
 * honesty test that pins its framing.
 */
export function DivergencePanel({
  meta,
  state,
  comparator,
  onComparator,
}: {
  meta: Meta;
  state: ApiState<DivergenceResponse>;
  comparator: string;
  onComparator: (key: string) => void;
}) {
  const theme = useChartTheme();
  const historical = meta.historical;
  const divergence = state.data;
  const framing = divergence?.framing ?? historical.framing.divergence;
  const pointer = divergence?.counterfactual_pointer ?? historical.framing.counterfactual_pointer;
  const label =
    divergence?.comparator_label ?? historical.comparators.find((c) => c.key === comparator)?.label ?? comparator;
  const anchor = divergence?.anchor_year ?? historical.divergence_anchor;
  const pathLabel = `Tracking ${label}'s growth since ${anchor} (illustrative)`;

  const byYear = new Map<number, Record<string, number | null | [number, number]>>();
  let lowFrom: number | null = null;
  let lowUntil: number | null = null;
  if (divergence) {
    const actual = divergence.series.map((p) => ({ year: p.year, value: p.actual, reliability: p.reliability }));
    lowUntil = splitByReliability(actual, "actual", byYear as Map<number, Record<string, number | null>>);
    const lows = divergence.series.filter((p) => p.reliability === "low").map((p) => p.year);
    lowFrom = lows.length > 0 ? Math.min(...lows) : null;
    for (const p of divergence.series) {
      const row = byYear.get(p.year) ?? { year: p.year };
      row.path = p.path;
      row.ratio = p.ratio;
      row.gap = p.actual != null && p.path != null ? [Math.min(p.actual, p.path), Math.max(p.actual, p.path)] : null;
      byYear.set(p.year, row);
    }
  }
  const full = [...byYear.values()].sort((a, b) => Number(a.year) - Number(b.year));
  // The scrubber grows both lines up to the chosen year; at rest it shows them whole.
  const playback = usePlayback(full.length);
  const scrubYear = Number(full[playback.index]?.year ?? anchor);
  const data = playback.scrubbed
    ? full.map((row) =>
        Number(row.year) <= scrubYear ? row : { year: Number(row.year), actual: null, actual__low: null, path: null, gap: null },
      )
    : full;
  const point = divergence?.series.find((p) => p.year === scrubYear);
  const metrics = divergence?.metrics;
  const others = divergence?.sensitivity.filter((s) => !s.default) ?? [];
  const ratios = divergence?.sensitivity.map((s) => s.ratio_latest) ?? [];
  const sensitivityNote =
    others.length > 0
      ? `Anchor-sensitive: started in ${others.map((s) => s.anchor_year).join(", ")} instead, the path ends at ${others
          .map((s) => ratio(s.ratio_latest))
          .join(", ")} actual.`
      : null;

  return (
    <div className="stack">
      <Banner tone="caution" title={ILLUSTRATIVE_TITLE} role="note">
        <p>{withoutLeadingTitle(framing, ILLUSTRATIVE_TITLE)}</p>
        <p>
          {pointer} <a href="#/counterfactual">Open the Counterfactual view</a>
        </p>
      </Banner>

      <ControlPanel
        label="Comparator"
        title="Track whose growth?"
        description={`The path starts at ${lowReliabilityRule(meta).name}'s actual ${anchor} level and grows at the comparator's actual annual rates.`}
      >
        <label className="select">
          <span>Comparator</span>
          <select value={comparator} onChange={(event) => onComparator(event.target.value)}>
            {historical.comparators.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </ControlPanel>

      {metrics ? (
        <StatRow>
          <StatCallout
            label={`${metrics.latest_year}: illustrative path ÷ actual`}
            value={ratio(metrics.ratio_latest)}
            count={{ value: metrics.ratio_latest, from: 1, format: (v) => (v == null ? "–" : ratio(v)) }}
            detail={`${formatDollars(metrics.path_latest)} on the path against ${formatDollars(metrics.actual_latest)} actual - an illustration, not an estimate`}
          />
          <StatCallout
            label="Anchor-sensitive"
            value={ratios.length > 0 ? `${ratio(Math.min(...ratios))}–${ratio(Math.max(...ratios))}` : "–"}
            detail={`The same path re-anchored in ${historical.sensitivity_anchors.join(", ")}`}
          />
          <StatCallout
            label={`Growth a year since ${metrics.anchor_year}`}
            value={`${formatPercent(metrics.actual_growth_pa, 1)} vs ${formatPercent(metrics.path_growth_pa, 1)}`}
            detail={`${lowReliabilityRule(meta).name} actual vs the ${label}-tracking path`}
          />
        </StatRow>
      ) : null}

      <ChartFrame
        title={`${lowReliabilityRule(meta).name} and an illustrative path: ${label}'s growth since ${anchor}`}
        subtitle="The shaded gap shows how far the two trajectories separated. It bundles every difference between the two - policy, conflict, prices, measurement - and attributes it to no cause."
        badge="Illustrative scenario"
        badgeTone="caution"
        status={state.loading && divergence ? "Updating…" : undefined}
        seriesLegend={[
          <LegendItem key="actual" color={theme.hero} label={`${lowReliabilityRule(meta).name}, actual`} variant="bold" />,
          <LegendItem key="path" color={theme.neutral} label="Illustrative path" variant="dashed" />,
        ]}
        legend={
          <>
            <LegendItem color={theme.neutral} label={pathLabel} variant="dashed" />
            <LegendItem color={theme.hero} label="Gap, shaded (illustrative)" variant="band" />
            {honestyKeys(meta, theme)}
          </>
        }
        notes={[...(divergence?.notes ?? []), sensitivityNote].filter((n): n is string => Boolean(n))}
        source="Source: World Bank, World Development Indicators (constant 2015 US$); Amber's illustrative path."
        summary={
          metrics
            ? `Line chart, log scale, ${anchor}–${metrics.latest_year}: ${lowReliabilityRule(meta).name}'s actual GDP per capita against an illustrative path that grows its ${anchor} level at ${label}'s actual growth rates. By ${metrics.latest_year} the path is ${ratio(metrics.ratio_latest)} the actual level (${formatDollars(metrics.path_latest)} against ${formatDollars(metrics.actual_latest)}). ${ILLUSTRATIVE_TITLE}. ${sensitivityNote ?? ""}`
            : `${ILLUSTRATIVE_TITLE}: the divergence path has not loaded yet.`
        }
        table={
          divergence
            ? {
                caption: `${lowReliabilityRule(meta).name}'s actual GDP per capita and the illustrative ${label}-tracking path (constant 2015 US$)`,
                columns: ["Year", "Actual", "Illustrative path", "Path ÷ actual", "Reliability (actual)"],
                rows: divergence.series.map((p) => [
                  String(p.year),
                  formatDollars(p.actual),
                  formatDollars(p.path),
                  p.ratio != null ? ratio(p.ratio) : "–",
                  p.reliability,
                ]),
              }
            : null
        }
      >
        <Async state={state} what="the divergence scenario" height={CHART.height} isEmpty={(d) => d.series.length === 0}>
          {() => (
            <>
              <DivergenceChart
                data={data}
                pathLabel={pathLabel}
                lowFrom={lowFrom}
                lowUntil={lowUntil}
                windowStart={meta.modeling_window.start}
                format={formatDollars}
                animate={!playback.scrubbed}
                cursorYear={playback.scrubbed ? scrubYear : null}
              />
              <div className="player">
                <TimeScrubber
                  years={full.map((row) => Number(row.year))}
                  playback={playback}
                  label={`Year of the divergence, ${anchor} to ${full.at(-1)?.year ?? ""}`}
                />
                {point ? (
                  <p className="player__readout num">
                    {`${point.year}: ${lowReliabilityRule(meta).name} ${formatDollars(point.actual)}${
                      point.reliability === "low" ? " (low reliability)" : ""
                    }, illustrative path ${formatDollars(point.path)}, ${point.ratio != null ? ratio(point.ratio) : "–"} actual.`}
                  </p>
                ) : null}
              </div>
            </>
          )}
        </Async>
      </ChartFrame>
    </div>
  );
}

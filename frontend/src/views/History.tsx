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
import { useI18n, type I18n } from "../i18n/context";
import { list, listAnd, ratio, reliabilityWord } from "../i18n/words";
import { CHART } from "../lib/chartTokens";
import { formatDollars, formatPercent, withoutLeadingTitle } from "../lib/format";
import { splitByReliability } from "../lib/shape";
import { useChartTheme } from "../lib/theme";

/** The historical arc: the 1960+ reconstruction, then the illustrative long-run divergence. */
export function History() {
  const meta = useMeta();
  const { t } = useI18n();
  const historical = meta.historical;
  const [comparator, setComparator] = useState(historical.default_comparator);
  const series = useApi((signal) => api.historical({}, signal), "historical");
  const divergence = useApi((signal) => api.divergence(comparator, signal), `divergence:${comparator}`);
  const treated = lowReliabilityRule(meta).name;

  return (
    <div className="view">
      <SectionHeader
        eyebrow={t("nav.history")}
        title={t("views.history.title", { country: treated, start: historical.window.start, end: historical.window.end })}
        description={t("views.history.description", { year: meta.modeling_window.start })}
      />

      <Reconstruction meta={meta} state={series} />

      <section className="section" aria-labelledby="divergence-title">
        <SectionHeader
          level={2}
          id="divergence-title"
          title={t("views.history.divergenceTitle")}
          description={t("views.history.divergenceDescription", { country: treated, year: historical.divergence_anchor })}
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
  return { name: treated?.name ?? meta.treated_country, until: rule?.standard_from ?? null };
}

/** The two honesty cues' legend keys - shown at every width, named so neither rests on color. */
function honestyKeys(i18n: I18n, meta: Meta, color: { hero: string; hatch: string; neutral: string }) {
  const { t } = i18n;
  const { name, until } = lowReliabilityRule(meta);
  return (
    <>
      {until != null ? (
        <>
          <LegendItem
            color={color.hero}
            label={t("honesty.lowReliabilityDotted", { country: name, year: until })}
            variant="dotted"
          />
          <LegendItem color={color.hatch} label={t("honesty.hatched")} variant="hatch" />
        </>
      ) : null}
      <LegendItem
        color={color.neutral}
        label={t("honesty.windowKey", { year: meta.modeling_window.start })}
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
  const i18n = useI18n();
  const { t } = i18n;
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
    t("views.history.markers", { events: events.map((e) => e.label).join(t("meta.middot")) }),
  ];
  const first = data[0]?.year;
  const last = data.at(-1)?.year;
  const spineName = spine?.name ?? "";
  const title = t("views.gdp.title", {
    name: spineName.replace(/ \(.*\)$/, ""),
    start: first ?? historical.window.start,
    end: last ?? historical.window.end,
  });
  const treatedValue = (row: Record<string, number | null>) => row[treated] ?? row[`${treated}__low`] ?? null;
  const firstRow = data.find((row) => treatedValue(row) != null);
  const lastRow = [...data].reverse().find((row) => treatedValue(row) != null);

  return (
    <section className="section" aria-labelledby="reconstruction-title">
      <ChartFrame
        title={title}
        subtitle={t("views.history.subtitle", {
          country: treatedName,
          others: list(i18n, comparators),
          units: spine?.units ?? "",
        })}
        callout={
          until != null ? (
            <Pill tone="caution">{t("honesty.lowReliabilityBefore", { country: treatedName, year: until })}</Pill>
          ) : null
        }
        status={state.loading && state.data ? t("banners.updating") : undefined}
        seriesLegend={series.map((s) => (
          <LegendItem key={s.key} color={s.hero ? theme.hero : theme.neutral} label={s.label} variant={s.hero ? "bold" : "line"} />
        ))}
        legend={honestyKeys(i18n, meta, theme)}
        notes={notes}
        source={t("views.history.source")}
        summary={[
          t("views.history.summary", {
            name: spineName,
            from: first ?? "–",
            to: last ?? "–",
            countries: listAnd(
              i18n,
              series.map((s) => s.label),
            ),
          }),
          firstRow && lastRow
            ? t("charts.endpoints", {
                country: treatedName,
                first: formatDollars(treatedValue(firstRow)),
                firstYear: Number(firstRow.year),
                last: formatDollars(treatedValue(lastRow)),
                lastYear: Number(lastRow.year),
              })
            : "",
          until != null ? t("honesty.lowReliabilitySummary", { country: treatedName, year: until }) : "",
          t("honesty.windowSummary", { year: meta.modeling_window.start }),
          t("views.history.markers", { events: list(i18n, events.map((e) => e.label)) }),
        ]
          .filter(Boolean)
          .join(" ")}
        table={data.length > 0 ? historicalTable(i18n, title, data, series, treated) : null}
      >
        <Async
          state={state}
          what={t("banners.what.historical")}
          height={CHART.height}
          isEmpty={(d) => d.rows.length === 0}
        >
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
  i18n: I18n,
  caption: string,
  data: Record<string, number | null>[],
  series: HistoricalSeries[],
  treated: string,
): TableSpec {
  const { t } = i18n;
  return {
    caption: t("views.history.tableCaption", { caption }),
    columns: [t("charts.year"), ...series.map((s) => s.label)],
    rows: data.map((row) => [
      String(row.year),
      ...series.map((s) => {
        const standard = row[s.key];
        const low = row[`${s.key}__low`];
        if (standard != null) return formatDollars(standard);
        if (low != null) {
          return s.key === treated ? t("charts.lowCell", { value: formatDollars(low) }) : formatDollars(low);
        }
        return "–";
      }),
    ]),
  };
}

/** The pre-1960 Maddison series - only when the snapshot holds it, on its own axis and ruler. */
function MaddisonFrame({ meta, rows }: { meta: Meta; rows: HistoricalResponse["rows"] }) {
  const theme = useChartTheme();
  const i18n = useI18n();
  const { t } = i18n;
  const indicator = meta.historical.indicators.find((i) => i.source === "maddison");
  const byYear = new Map<number, Record<string, number | null>>();
  const iso3 = rows[0]?.country_iso3 ?? "";
  splitByReliability(rows, iso3, byYear);
  const data = [...byYear.values()].sort((a, b) => Number(a.year) - Number(b.year));
  const name = meta.historical.countries.find((c) => c.iso3 === iso3)?.name ?? iso3;
  const years = rows.map((r) => r.year);
  const lows = rows.filter((r) => r.reliability === "low").map((r) => r.year);
  const units = indicator?.units ?? "";
  return (
    <ChartFrame
      title={t("views.history.maddisonTitle", { year: meta.historical.window.start, country: name })}
      subtitle={t("views.history.maddisonSubtitle", { units })}
      badge={t("honesty.differentUnits", { units })}
      badgeTone="neutral"
      legend={<LegendItem color={theme.hatch} label={t("honesty.hatched")} variant="hatch" />}
      notes={[meta.historical.framing.maddison, meta.historical.framing.low_reliability]}
      source={t("views.history.maddisonSource")}
      summary={t("views.history.maddisonSummary", {
        country: name,
        units,
        from: Math.min(...years),
        to: Math.max(...years),
      })}
      table={{
        caption: t("views.history.maddisonTable", { country: name, units }),
        columns: [
          t("charts.year"),
          t("views.history.maddisonColumn", { country: name, units }),
          t("views.history.reliability"),
        ],
        rows: rows.map((r) => [String(r.year), formatDollars(r.value), reliabilityWord(i18n, r.reliability)]),
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
  const i18n = useI18n();
  const { t } = i18n;
  const historical = meta.historical;
  const divergence = state.data;
  const illustrativeTitle = t("honesty.illustrativeScenarioTitle");
  const framing = divergence?.framing ?? historical.framing.divergence;
  const pointer = divergence?.counterfactual_pointer ?? historical.framing.counterfactual_pointer;
  const label =
    divergence?.comparator_label ?? historical.comparators.find((c) => c.key === comparator)?.label ?? comparator;
  const anchor = divergence?.anchor_year ?? historical.divergence_anchor;
  const country = lowReliabilityRule(meta).name;
  const pathLabel = t("views.history.pathLabel", { comparator: label, year: anchor });

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
      ? t("views.history.sensitivity", {
          years: list(
            i18n,
            others.map((s) => String(s.anchor_year)),
          ),
          ratios: list(
            i18n,
            others.map((s) => ratio(i18n, s.ratio_latest)),
          ),
        })
      : null;

  return (
    <div className="stack">
      <Banner tone="caution" title={illustrativeTitle} role="note" kind="framing">
        <p>{withoutLeadingTitle(framing, illustrativeTitle)}</p>
        <p>
          {pointer} <a href="#/counterfactual">{t("views.history.openCounterfactual")}</a>
        </p>
      </Banner>

      <ControlPanel
        label={t("controls.comparator")}
        title={t("controls.trackWhose")}
        description={t("views.history.comparatorDescription", { country, year: anchor })}
      >
        <label className="select">
          <span>{t("controls.comparator")}</span>
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
            label={t("views.history.ratioLabel", { year: metrics.latest_year })}
            value={ratio(i18n, metrics.ratio_latest)}
            count={{ value: metrics.ratio_latest, from: 1, format: (v) => (v == null ? "–" : ratio(i18n, v)) }}
            detail={t("honesty.illustrationNotEstimate", {
              path: formatDollars(metrics.path_latest),
              actual: formatDollars(metrics.actual_latest),
            })}
          />
          <StatCallout
            label={t("views.history.anchorSensitive")}
            value={ratios.length > 0 ? `${ratio(i18n, Math.min(...ratios))}–${ratio(i18n, Math.max(...ratios))}` : "–"}
            detail={t("views.history.anchorDetail", {
              years: list(
                i18n,
                historical.sensitivity_anchors.map(String),
              ),
            })}
          />
          <StatCallout
            label={t("views.history.growthLabel", { year: metrics.anchor_year })}
            value={t("views.history.growthValue", {
              actual: formatPercent(metrics.actual_growth_pa, 1),
              path: formatPercent(metrics.path_growth_pa, 1),
            })}
            detail={t("views.history.growthDetail", { country, comparator: label })}
          />
        </StatRow>
      ) : null}

      <ChartFrame
        title={t("views.history.chartTitle", { country, comparator: label, year: anchor })}
        subtitle={t("honesty.gapAttributesNoCause")}
        badge={t("honesty.illustrativeScenario")}
        badgeTone="caution"
        status={state.loading && divergence ? t("banners.updating") : undefined}
        seriesLegend={[
          <LegendItem key="actual" color={theme.hero} label={t("charts.actual", { country })} variant="bold" />,
          <LegendItem key="path" color={theme.neutral} label={t("charts.illustrativePath")} variant="dashed" />,
        ]}
        legend={
          <>
            <LegendItem color={theme.neutral} label={pathLabel} variant="dashed" />
            <LegendItem color={theme.hero} label={t("charts.gapShaded")} variant="band" />
            {honestyKeys(i18n, meta, theme)}
          </>
        }
        notes={[...(divergence?.notes ?? []), sensitivityNote].filter((n): n is string => Boolean(n))}
        source={t("views.history.chartSource")}
        summary={
          metrics
            ? t("views.history.chartSummary", {
                from: anchor,
                to: metrics.latest_year,
                country,
                comparator: label,
                ratio: ratio(i18n, metrics.ratio_latest),
                path: formatDollars(metrics.path_latest),
                actual: formatDollars(metrics.actual_latest),
                title: illustrativeTitle,
                sensitivity: sensitivityNote ?? "",
              })
            : t("views.history.chartSummaryLoading", { title: illustrativeTitle })
        }
        table={
          divergence
            ? {
                caption: t("views.history.divergenceTable", { country, comparator: label }),
                columns: [
                  t("charts.year"),
                  t("views.history.actualColumn"),
                  t("charts.illustrativePath"),
                  t("views.history.ratioColumn"),
                  t("views.history.reliabilityColumn"),
                ],
                rows: divergence.series.map((p) => [
                  String(p.year),
                  formatDollars(p.actual),
                  formatDollars(p.path),
                  p.ratio != null ? ratio(i18n, p.ratio) : "–",
                  reliabilityWord(i18n, p.reliability),
                ]),
              }
            : null
        }
      >
        <Async
          state={state}
          what={t("banners.what.divergence")}
          height={CHART.height}
          isEmpty={(d) => d.series.length === 0}
        >
          {() => (
            <>
              <DivergenceChart
                data={data}
                country={country}
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
                  label={t("views.history.scrubLabel", { from: anchor, to: full.length > 0 ? Number(full.at(-1)?.year) : "" })}
                />
                {point ? (
                  <p className="player__readout num">
                    {t(point.reliability === "low" ? "views.history.readoutLow" : "views.history.readout", {
                      year: point.year,
                      country,
                      actual: formatDollars(point.actual),
                      path: formatDollars(point.path),
                      ratio: point.ratio != null ? ratio(i18n, point.ratio) : "–",
                    })}
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

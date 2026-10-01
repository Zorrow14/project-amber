import { api } from "../api/client";
import type { Meta } from "../api/types";
import { ChartCard, LegendItem } from "../components/ChartCard";
import { Async } from "../components/LoadState";
import { CountryLinesChart } from "../charts/CountryLinesChart";
import { useApi } from "../hooks/useApi";
import { describeCountryLines, seriesTable } from "../lib/describe";
import { formatDollars } from "../lib/format";
import { pivot } from "../lib/shape";
import { seriesColor, useChartTheme } from "../lib/theme";

/** Real GDP per capita for every country - the headline divergence. */
export function GdpDivergence({ meta, subtitle }: { meta: Meta; subtitle?: string }) {
  const theme = useChartTheme();
  const gdp = meta.sc_outcomes.find((o) => o.is_currency) ?? meta.sc_outcomes[0];
  const indicatorId = gdp?.id ?? "";
  const indicator = meta.indicators.find((i) => i.id === indicatorId);
  const panel = useApi((signal) => api.panel({ indicators: [indicatorId] }, signal), `panel:${indicatorId}`);

  const data = panel.data
    ? pivot(
        panel.data.rows,
        (r) => r.year,
        (r) => r.country_iso3,
        (r) => r.value,
      )
    : [];
  const imputed = panel.data?.rows.filter((r) => r.imputed).length ?? 0;
  const treated = meta.countries.find((c) => c.treated);
  const donors = meta.countries.filter((c) => c.donor).length;
  const name = indicator?.name ?? "GDP per capita";
  const what = `${name} (constant 2015 US$, log scale)`;

  return (
    <ChartCard
      title={`${name}, ${meta.modeling_window.start}–${meta.modeling_window.end}`}
      subtitle={
        subtitle ??
        `${treated?.name ?? "Myanmar"} against the ${donors} peers of the donor pool. Log scale, so equal slopes are equal growth rates.`
      }
      legend={meta.countries.map((c, i) => (
        <LegendItem key={c.iso3} color={seriesColor(theme, i)} label={c.name} variant={c.treated ? "bold" : "line"} />
      ))}
      notes={[
        `Source: World Bank WDI. ${meta.framing.fiscal_year}`,
        imputed > 0 ? `${imputed} values are interpolated across interior gaps, not observed.` : null,
      ].filter((n): n is string => Boolean(n))}
      summary={`${describeCountryLines(what, data, meta.countries, formatDollars)} ${meta.framing.fiscal_year}`}
      table={
        data.length > 0
          ? seriesTable(
              `${name} by year and country (constant 2015 US$)`,
              data,
              meta.countries.map((c) => ({ key: c.iso3, label: c.name })),
              formatDollars,
            )
          : null
      }
    >
      <Async state={panel} what="the GDP series" height={280} isEmpty={(d) => d.rows.length === 0}>
        {() => <CountryLinesChart meta={meta} data={data} format={formatDollars} logScale yLabel="2015 US$ (log)" />}
      </Async>
    </ChartCard>
  );
}

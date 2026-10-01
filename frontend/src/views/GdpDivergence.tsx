import { api } from "../api/client";
import type { Meta } from "../api/types";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { Async } from "../components/LoadState";
import { CountryLinesChart } from "../charts/CountryLinesChart";
import { useApi } from "../hooks/useApi";
import { CHART } from "../lib/chartTokens";
import { describeCountryLines, seriesTable } from "../lib/describe";
import { formatDollars } from "../lib/format";
import { pivot } from "../lib/shape";
import { countryColors, useChartTheme } from "../lib/theme";

/** Real GDP per capita for every country - the headline divergence. */
export function GdpDivergence({ meta, subtitle }: { meta: Meta; subtitle?: string }) {
  const theme = useChartTheme();
  const colors = countryColors(theme, meta.countries);
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
    <ChartFrame
      title={`${name}, ${meta.modeling_window.start}–${meta.modeling_window.end}`}
      subtitle={
        subtitle ??
        `${treated?.name ?? "Myanmar"} against the ${donors} peers of the donor pool. Constant 2015 US$ on a log scale, so equal slopes are equal growth rates.`
      }
      seriesLegend={meta.countries.map((c) => (
        <LegendItem
          key={c.iso3}
          color={colors.get(c.iso3) ?? theme.neutral}
          label={c.name}
          variant={c.treated ? "bold" : "line"}
        />
      ))}
      notes={[
        meta.framing.fiscal_year,
        imputed > 0 ? `${imputed} values are interpolated across interior gaps, not observed.` : null,
      ].filter((n): n is string => Boolean(n))}
      source="Source: World Bank, World Development Indicators."
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
      <Async state={panel} what="the GDP series" height={CHART.heightNarrow} isEmpty={(d) => d.rows.length === 0}>
        {() => <CountryLinesChart meta={meta} data={data} format={formatDollars} logScale />}
      </Async>
    </ChartFrame>
  );
}

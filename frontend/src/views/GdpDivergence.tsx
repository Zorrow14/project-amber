import { api } from "../api/client";
import type { Meta } from "../api/types";
import { ChartFrame, LegendItem } from "../components/ChartFrame";
import { Async } from "../components/LoadState";
import { CountryLinesChart } from "../charts/CountryLinesChart";
import { useApi } from "../hooks/useApi";
import { useI18n } from "../i18n/context";
import { CHART } from "../lib/chartTokens";
import { describeCountryLines, seriesTable } from "../lib/describe";
import { formatDollars } from "../lib/format";
import { pivot } from "../lib/shape";
import { countryColors, useChartTheme } from "../lib/theme";

/** Real GDP per capita for every country - the headline divergence. */
export function GdpDivergence({ meta, subtitle }: { meta: Meta; subtitle?: string }) {
  const theme = useChartTheme();
  const i18n = useI18n();
  const { t } = i18n;
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
  const name = indicator?.name ?? gdp?.label ?? indicatorId;
  const what = t("views.gdp.what", { name });

  return (
    <ChartFrame
      title={t("views.gdp.title", { name, start: meta.modeling_window.start, end: meta.modeling_window.end })}
      subtitle={subtitle ?? t("views.gdp.subtitle", { country: treated?.name ?? meta.treated_country, n: donors })}
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
        imputed > 0 ? t("views.gdp.interpolated", { n: imputed }) : null,
      ].filter((n): n is string => Boolean(n))}
      source={t("charts.sourceWdi")}
      summary={`${describeCountryLines(i18n, what, data, meta.countries, formatDollars)} ${meta.framing.fiscal_year}`}
      table={
        data.length > 0
          ? seriesTable(
              i18n,
              t("views.gdp.tableCaption", { name }),
              data,
              meta.countries.map((c) => ({ key: c.iso3, label: c.name })),
              formatDollars,
            )
          : null
      }
    >
      <Async
        state={panel}
        what={t("banners.what.gdp")}
        height={CHART.heightNarrow}
        isEmpty={(d) => d.rows.length === 0}
      >
        {() => <CountryLinesChart meta={meta} data={data} format={formatDollars} logScale />}
      </Async>
    </ChartFrame>
  );
}

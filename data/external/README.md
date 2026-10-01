# External data

Files here come from outside the World Bank API and are supplied by hand. Each one is optional: if it is absent, the pipeline skips it and logs why. Nothing in this folder is fabricated or typed in. Each file is an unmodified export of a published dataset.

## `maddison_myanmar.csv` (optional)

This file draws the pre-1960 segment of the historical GDP-per-capita chart (`make historical`). It comes from the **Maddison Project Database, version 2023**:

> Bolt, Jutta and Jan Luiten van Zanden (2024), "Maddison style estimates of the evolution of the world economy: A new 2023 update", *Journal of Economic Surveys*, 1–41. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**How to export it:**

1. Download `mpd2023_web.xlsx` from the [Maddison Project Database 2023 page](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) (Groningen Growth and Development Centre).
2. Open the **`Full data`** sheet and filter `countrycode` to `MMR`.
3. Save those rows, header included, as `data/external/maddison_myanmar.csv`. Keep the sheet's column names: at least `countrycode`, `year` and `gdppc` (the other columns are ignored). Do not edit any values.
4. Run `make historical`.

**How it is used, and how it is not:**

- `gdppc` is GDP per capita in **2011 international dollars at PPP**. That is a different ruler from the World Bank's constant 2015 US$, so the two are never spliced into one series. Maddison rows get their own indicator id (`maddison.gdppc`) and source tag (`maddison`). The chart draws them in a separate panel with its own axis.
- Only years **before 1960** are kept (`MADDISON_LAST_YEAR`). From 1960 the World Bank series is the spine, so the two rulers never overlap.
- Every Myanmar observation before 1990 is flagged low reliability (`RELIABILITY_LOW_BEFORE`), and that includes all Maddison rows. Myanmar's pre-1950 estimates are sparse benchmark years. Read them as orders of magnitude.
- The divergence scenario reads only the World Bank series. Adding this file never changes any other table or figure.

If you commit the file, keep the citation above alongside it, as CC BY 4.0 requires.

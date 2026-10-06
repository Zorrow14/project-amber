/**
 * Where Amber's data, standards and methods come from, and where to read more.
 * Citations are bibliographic data, kept in their published (English) form in
 * every language; what each source is used for is a message (`sources.entries.*`).
 * Keep this in step with the README's "Data and attribution".
 */

export const REPO_URL = "https://github.com/Zorrow14/project-amber";

export const LINKS = {
  methodology: `${REPO_URL}/blob/main/docs/METHODOLOGY.md`,
  limitations: `${REPO_URL}/blob/main/docs/LIMITATIONS.md`,
  code: REPO_URL,
  maker: "https://htet-aung-lwin-portfolio.vercel.app",
} as const;

export const CC_BY = { name: "CC BY 4.0", url: "https://creativecommons.org/licenses/by/4.0/" } as const;

export type SourceId = "wdi" | "maddison" | "undp" | "sdsn" | "imf" | "msdp" | "scm" | "czernich" | "acled" | "hdi";
export type SourceGroupId = "data" | "standards" | "crossChecks" | "plans" | "methods" | "notUsed";

export interface Source {
  id: SourceId;
  citation: string;
  url: string;
  licence?: { name: string; url: string };
}

/** Grouped by the role each source plays, so none is credited with more than it does. */
export const SOURCE_GROUPS: { id: SourceGroupId; sources: Source[] }[] = [
  {
    id: "data",
    sources: [
      {
        id: "wdi",
        citation: "World Bank, World Development Indicators (WDI)",
        url: "https://datatopics.worldbank.org/world-development-indicators/",
        licence: CC_BY,
      },
      {
        id: "maddison",
        citation: "Maddison Project Database, version 2023 (Bolt and van Zanden 2024)",
        url: "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
        licence: CC_BY,
      },
    ],
  },
  {
    id: "standards",
    sources: [
      {
        id: "undp",
        citation: "UNDP, Human Development Report 2025, Technical Notes",
        url: "https://hdr.undp.org/data-center/documentation-and-downloads",
      },
      {
        id: "sdsn",
        citation: "Sustainable Development Solutions Network, Sustainable Development Report 2026",
        url: "https://dashboards.sdgindex.org/",
      },
    ],
  },
  {
    id: "crossChecks",
    sources: [{ id: "imf", citation: "IMF, World Economic Outlook", url: "https://www.imf.org/en/Publications/WEO" }],
  },
  {
    id: "plans",
    sources: [
      {
        id: "msdp",
        citation: "Government of Myanmar, Myanmar Sustainable Development Plan 2018–2030 (MSDP)",
        url: "https://themimu.info/sites/themimu.info/files/documents/Core_Doc_Myanmar_Sustainable_Development_Plan_2018_-_2030_Aug2018.pdf",
      },
    ],
  },
  {
    id: "methods",
    sources: [
      {
        id: "scm",
        citation:
          "Abadie, Diamond and Hainmueller (2010), “Synthetic Control Methods for Comparative Case Studies”, Journal of the American Statistical Association 105(490)",
        url: "https://doi.org/10.1198/jasa.2009.ap08746",
      },
      {
        id: "czernich",
        citation:
          "Czernich, Falck, Kretschmer and Woessmann (2011), “Broadband Infrastructure and Economic Growth”, Economic Journal 121(552)",
        url: "https://ideas.repec.org/a/ecj/econjl/v121y2011i552p505-532.html",
      },
    ],
  },
  {
    id: "notUsed",
    sources: [
      { id: "acled", citation: "ACLED, Armed Conflict Location & Event Data", url: "https://acleddata.com/" },
      {
        id: "hdi",
        citation: "UNDP, Human Development Index",
        url: "https://hdr.undp.org/data-center/human-development-index",
      },
    ],
  },
];

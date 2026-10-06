import { useRef } from "react";

import { useAnchorTarget } from "../context/routeContext";
import { useI18n } from "../i18n/context";
import { SOURCE_GROUPS } from "../lib/sources";
import { SOURCES_ANCHOR } from "../lib/url";
import { Card } from "./Card";
import { SectionHeader } from "./SectionHeader";

/**
 * Sources & citations: every source Amber draws on, grouped by the role it
 * plays (data in the app, standards cited, cross-checks, scenario directions,
 * methods, and what is not used), so none is credited with more than it does.
 * Citations keep their published form and are marked English; what each is
 * used for is translated.
 */
export function Sources() {
  const { t, tNodes } = useI18n();
  const ref = useRef<HTMLElement>(null);
  useAnchorTarget(SOURCES_ANCHOR, ref);

  return (
    <section className="section sources" id={SOURCES_ANCHOR} ref={ref} tabIndex={-1} aria-labelledby="sources-title">
      <SectionHeader level={2} id="sources-title" title={t("sources.title")} description={t("sources.description")} />
      <Card subtle>
        <div className="sources__groups">
          {SOURCE_GROUPS.map((group) => (
            <section key={group.id} className="sources__group" aria-labelledby={`sources-${group.id}`}>
              <h3 className="sources__group-title" id={`sources-${group.id}`}>
                {t(`sources.groups.${group.id}`)}
              </h3>
              <ul className="sources__list">
                {group.sources.map((source) => (
                  <li key={source.id} className="source">
                    <cite className="source__citation" lang="en">
                      <a href={source.url}>{source.citation}</a>
                    </cite>
                    <span className="source__use">{t(`sources.entries.${source.id}`)}</span>
                    {source.licence ? (
                      <span className="source__licence">
                        {tNodes("sources.licence", {
                          licence: (
                            <a href={source.licence.url} lang="en">
                              {source.licence.name}
                            </a>
                          ),
                        })}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </Card>
    </section>
  );
}

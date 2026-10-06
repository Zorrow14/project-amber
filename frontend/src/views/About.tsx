import { Banner, Pill } from "../components/Banner";
import { Icon } from "../components/Icon";
import { SectionHeader } from "../components/SectionHeader";
import { Sources } from "../components/Sources";
import { Link } from "../context/route";
import { useI18n } from "../i18n/context";
import type { MessageKey } from "../i18n/catalog";
import { LINKS } from "../lib/sources";
import type { View } from "../lib/url";

/** The three questions, each with the views that answer it. */
const QUESTIONS: { view: View; text: MessageKey; open: View[] }[] = [
  { view: "past", text: "views.about.past", open: ["past", "history"] },
  { view: "counterfactual", text: "views.about.counterfactual", open: ["counterfactual"] },
  { view: "future", text: "views.about.future", open: ["future"] },
];

const LEARN_MORE = ["methodology", "limitations", "code", "maker"] as const;

/**
 * What Amber is and how to read it: the landing view. It needs nothing from the
 * API, so it renders while a cold server wakes. Its honesty passages are the
 * point of the page; while their translation is a draft, each says so.
 */
export function About() {
  const { t, needsReview } = useI18n();
  // A draft marker for a section whose translation still awaits a Burmese speaker.
  const draft = (...keys: MessageKey[]) =>
    keys.some(needsReview) ? (
      <p className="about__draft">
        <Icon name="partial" />
        <span>{t("views.about.draft")}</span>
      </p>
    ) : null;
  const caveats: { text: string; tone: "critical" | "neutral" | "caution" }[] = [
    { text: t("honesty.illustrativeOnly"), tone: "critical" },
    { text: t("honesty.scenarioBadge"), tone: "neutral" },
    { text: t("honesty.partialCoverage"), tone: "caution" },
    { text: sentenceCase(t("honesty.lowReliability")), tone: "caution" },
  ];

  return (
    <div className="view about">
      <SectionHeader title={t("views.about.title")} description={t("views.about.intro")} />

      <section className="section" aria-labelledby="about-views">
        <SectionHeader
          level={2}
          id="about-views"
          title={t("views.about.lookingTitle")}
          description={t("views.about.lookingIntro")}
        />
        <ul className="layers about__questions">
          {QUESTIONS.map((question) => (
            <li key={question.view} className="card about__question">
              <h3 className="layer__title">{t(`nav.${question.view}`)}</h3>
              <p className="layer__method">{t(question.text)}</p>
              <p className="about__open">
                {question.open.map((view) => (
                  <Link key={view} view={view} className="layer__cta">
                    {t("views.overview.open", { view: t(`nav.${view}`).toLowerCase() })}
                  </Link>
                ))}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="section" aria-labelledby="about-honesty">
        <SectionHeader level={2} id="about-honesty" title={t("views.about.honestyTitle")} />
        {draft("views.about.honestyLead", "views.about.estimateBody", "views.about.scenarioBody", "views.about.caveats")}
        <Banner tone="info" title={t("views.about.honestyLead")} kind="framing">
          <p>{t("views.about.keepInMind")}</p>
          <ul className="about__points">
            <li>
              <strong>{t("views.about.estimateLead")}</strong> {t("views.about.estimateBody")}
            </li>
            <li>
              <strong>{t("views.about.scenarioLead")}</strong> {t("views.about.scenarioBody")}
            </li>
          </ul>
        </Banner>
        <p className="about__prose">{t("views.about.caveats")}</p>
        <ul className="about__caveats" aria-label={t("views.about.caveatExamples")}>
          {caveats.map((caveat) => (
            <li key={caveat.text}>
              <Pill tone={caveat.tone}>{caveat.text}</Pill>
            </li>
          ))}
        </ul>
      </section>

      <section className="section" aria-labelledby="about-neutrality">
        <SectionHeader level={2} id="about-neutrality" title={t("views.about.neutralityTitle")} />
        {draft("views.about.neutrality")}
        <p className="about__prose">{t("views.about.neutrality")}</p>
      </section>

      <section className="section" aria-labelledby="about-data">
        <SectionHeader level={2} id="about-data" title={t("views.about.dataTitle")} />
        {draft("views.about.data")}
        <p className="about__prose">{t("views.about.data")}</p>
      </section>

      <Sources />

      <section className="section" aria-labelledby="about-learn">
        <SectionHeader level={2} id="about-learn" title={t("views.about.learnTitle")} />
        <ul className="about__learn">
          {LEARN_MORE.map((name) => (
            <li key={name}>
              <a href={LINKS[name]}>{t(`views.about.${name}`)}</a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** A caveat written mid-sentence ("low reliability") as a tag; scripts without case are unchanged. */
function sentenceCase(text: string): string {
  return text.charAt(0).toLocaleUpperCase("en-US") + text.slice(1);
}

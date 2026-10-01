import type { ReactNode } from "react";

/**
 * Eyebrow -> title -> description: the one rhythm every view and section shares.
 * `level` 1 is the view's single H1 (`display` for the overview headline), 2 a
 * section within it.
 */
export function SectionHeader({
  eyebrow,
  title,
  description,
  level = 1,
  display = false,
  id,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  level?: 1 | 2;
  display?: boolean;
  id?: string;
}) {
  const Heading = level === 1 ? "h1" : "h2";
  const size = display ? "display" : level === 1 ? "h1" : "h2";
  return (
    <header className="section-header">
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <Heading className={`section-header__title section-header__title--${size}`} id={id}>
        {title}
      </Heading>
      {description ? (
        <p className={`section-header__description${level === 2 ? " section-header__description--sm" : ""}`}>
          {description}
        </p>
      ) : null}
    </header>
  );
}

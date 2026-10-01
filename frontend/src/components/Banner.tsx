import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

export type Tone = "info" | "caution" | "critical";

const ICON: Record<Tone, IconName> = { info: "info", caution: "partial", critical: "alert" };

/**
 * A labelled message - the scenario framing, the not-credible verdict, a failed
 * fetch. Tone is carried by an icon and a title as well as color, and it stays
 * calm: legible and unmissable, never alarming.
 */
export function Banner({
  tone,
  title,
  children,
  role,
}: {
  tone: Tone;
  title: string;
  children?: ReactNode;
  role?: "alert" | "status" | "note";
}) {
  return (
    <div className={`banner banner--${tone}`} role={role ?? (tone === "info" ? "note" : "alert")}>
      <Icon name={ICON[tone]} className="banner__icon" />
      <div className="banner__content">
        <strong className="banner__title">{title}</strong>
        {children ? <div className="banner__body">{children}</div> : null}
      </div>
    </div>
  );
}

/** Actions under a banner's text (retry, reload). */
export function BannerActions({ children }: { children: ReactNode }) {
  return <div className="banner__actions">{children}</div>;
}

export type PillTone = "neutral" | "caution" | "critical" | "status";

const PILL_ICON: Partial<Record<PillTone, IconName>> = { caution: "partial", critical: "alert", neutral: "info" };

/**
 * A compact label: a chart's caveat ("Illustrative only", "Scenario, not a
 * forecast"), a coverage flag, or a transient status ("Updating…").
 */
export function Pill({
  tone = "neutral",
  children,
  hidden,
  ...data
}: {
  tone?: PillTone;
  children?: ReactNode;
  hidden?: boolean;
  "data-caveat"?: boolean;
  "data-status"?: boolean;
  role?: "status";
}) {
  const icon = PILL_ICON[tone];
  return (
    <span className={`pill pill--${tone}`} hidden={hidden} {...data}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </span>
  );
}

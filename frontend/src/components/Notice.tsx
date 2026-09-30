import type { ReactNode } from "react";

type Tone = "info" | "warning" | "critical";

const ICONS: Record<Tone, string> = { info: "i", warning: "!", critical: "!" };

/** A labelled notice: tone is carried by an icon and a heading, never by color alone. */
export function Notice({
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
    <div className={`notice notice--${tone}`} role={role ?? (tone === "info" ? "note" : "alert")}>
      <span className="notice__icon" aria-hidden="true">
        {ICONS[tone]}
      </span>
      <div>
        <strong className="notice__title">{title}</strong>
        {children ? <div className="notice__body">{children}</div> : null}
      </div>
    </div>
  );
}

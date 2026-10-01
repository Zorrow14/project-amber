import type { ReactNode } from "react";

/** A surface with a hairline border and generous padding. */
export function Card({
  children,
  subtle = false,
  as: Tag = "div",
  label,
}: {
  children: ReactNode;
  subtle?: boolean;
  as?: "div" | "section" | "aside";
  label?: string;
}) {
  return (
    <Tag className={subtle ? "card card--subtle" : "card"} aria-label={label}>
      {children}
    </Tag>
  );
}

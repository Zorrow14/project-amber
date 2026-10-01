import type { ReactNode } from "react";

import { AnimatedNumber } from "./AnimatedNumber";

/**
 * A headline number: a small label, the figure set large in tabular digits, and
 * its context. With `count`, the figure counts up to its value on first view and
 * eases between values after that (instantly under reduced motion); `value` is
 * then the final text, which screen readers read.
 */
export function StatCallout({
  label,
  value,
  detail,
  count,
}: {
  label: string;
  value: string;
  detail?: string;
  count?: { value: number | null; format: (value: number | null) => string; from?: number; duration?: number };
}) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">
        {count ? <AnimatedNumber value={count.value} format={count.format} from={count.from} duration={count.duration} /> : value}
      </span>
      {detail ? <span className="stat__detail">{detail}</span> : null}
    </div>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="stats">{children}</div>;
}

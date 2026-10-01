import type { ReactNode } from "react";

/** A headline number: a small label, the figure set large in tabular digits, and its context. */
export function StatCallout({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {detail ? <span className="stat__detail">{detail}</span> : null}
    </div>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="stats">{children}</div>;
}

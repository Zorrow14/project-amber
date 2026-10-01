import type { ReactNode } from "react";

/**
 * One panel for a view's controls, kept apart from the chart they drive: a
 * title, a line on what the controls do, an optional reset, then the controls.
 */
export function ControlPanel({
  title,
  description,
  action,
  label,
  children,
  layout = "stack",
}: {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
  label: string;
  children: ReactNode;
  layout?: "stack" | "grid";
}) {
  return (
    <section className="card control-panel" aria-label={label}>
      {title || action ? (
        <div className="control-panel__head">
          <div>
            {title ? <h2 className="control-panel__title">{title}</h2> : null}
            {description ? <p className="control-panel__description">{description}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      <div className={layout === "grid" ? "control-panel__grid" : "control-panel__group"}>{children}</div>
    </section>
  );
}

/** A titled group inside a ControlPanel. */
export function ControlGroup({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="control-panel__group">
      <div className="control-panel__head">
        <div>
          <h3 className="control-panel__title">{title}</h3>
          {description ? <p className="control-panel__description">{description}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

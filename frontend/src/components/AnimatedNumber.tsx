import { useTween } from "../hooks/useTween";

/**
 * A number that counts to its value, in tabular figures so the width holds
 * still. Screen readers get only the final value; the moving digits are hidden
 * from them. Under reduced motion the final value renders at once.
 */
export function AnimatedNumber({
  value,
  format,
  from,
  duration,
}: {
  value: number | null;
  format: (value: number | null) => string;
  from?: number;
  duration?: number;
}) {
  const shown = useTween(value, { from, duration });
  return (
    <>
      <span className="num" aria-hidden="true" data-animated-number>
        {format(shown)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </>
  );
}

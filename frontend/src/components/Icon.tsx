/**
 * A few inline icons (16-unit grid, stroked with currentColor) so status never
 * rests on color alone and no icon library is needed. Decorative: hidden from
 * assistive tech, the adjacent text carries the meaning.
 */
const PATHS = {
  info: "M8 14.5A6.5 6.5 0 1 0 8 1.5a6.5 6.5 0 0 0 0 13ZM8 7.25v4M8 4.75v.01",
  alert: "M8 2 1.75 13h12.5L8 2ZM8 6.5v3M8 11.5v.01",
  partial: "M8 14.5A6.5 6.5 0 1 0 8 1.5a6.5 6.5 0 0 0 0 13ZM8 1.5v13",
  sun: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3.05 3.05l1.06 1.06M11.89 11.89l1.06 1.06M3.05 12.95l1.06-1.06M11.89 4.11l1.06-1.06",
  moon: "M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z",
  arrow: "M3 8h10M9 4l4 4-4 4",
  scale: "M8 2v12M3 5h10M3 5l-1.75 4.5a2 2 0 0 0 3.5 0L3 5Zm10 0-1.75 4.5a2 2 0 0 0 3.5 0L13 5ZM5.5 14h5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

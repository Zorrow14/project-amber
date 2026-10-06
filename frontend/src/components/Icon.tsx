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
  play: "M5 3.25v9.5L12.5 8 5 3.25Z",
  pause: "M5.5 3.5v9M10.5 3.5v9",
  scale: "M8 2v12M3 5h10M3 5l-1.75 4.5a2 2 0 0 0 3.5 0L3 5Zm10 0-1.75 4.5a2 2 0 0 0 3.5 0L13 5ZM5.5 14h5",
  link: "M6.75 9.25a2.75 2.75 0 0 0 3.9 0l2.1-2.1a2.75 2.75 0 0 0-3.9-3.9l-.6.6M9.25 6.75a2.75 2.75 0 0 0-3.9 0l-2.1 2.1a2.75 2.75 0 0 0 3.9 3.9l.6-.6",
  check: "M3 8.5 6.5 12 13 4.5",
  download: "M8 2v8.5M4.75 7.25 8 10.5l3.25-3.25M2.5 13.5h11",
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

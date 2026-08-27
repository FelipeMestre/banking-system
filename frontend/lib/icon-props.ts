/**
 * Shared Lucide props enforcing Modernist's squared icon geometry
 * (stroke-width 2, square linecaps) — set once here rather than on every
 * icon usage, per the design system's own instruction to set these globally
 * instead of copying the design mock's hand-written SVG paths.
 */
export const DS_ICON_PROPS = {
  strokeWidth: 2,
  strokeLinecap: "square" as const,
};

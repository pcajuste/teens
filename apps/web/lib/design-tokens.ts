/**
 * Design token reference — Section 0A of Teenure_Build_Prompts.md.
 *
 * The tokens themselves live as CSS custom properties in app/globals.css
 * (colors, radius) and are consumed via Tailwind utility classes
 * (bg-primary, text-muted-foreground, rounded-lg, etc.) — this file is
 * the documented, typed reference for the non-CSS-variable parts of the
 * system (type scale, spacing scale) so screens are built against a
 * shared vocabulary instead of arbitrary per-component values.
 *
 * Do not hardcode hex/oklch colors or one-off spacing values in
 * component code. If a value isn't expressible with what's here or in
 * globals.css, that's a sign the token system needs a deliberate
 * addition, not a one-off escape hatch.
 */

/** Type scale. Use as Tailwind class strings, e.g. `className={typeScale.h1}`. */
export const typeScale = {
  display: "text-4xl sm:text-5xl font-semibold tracking-tight",
  h1: "text-2xl sm:text-3xl font-semibold tracking-tight",
  h2: "text-xl sm:text-2xl font-semibold tracking-tight",
  h3: "text-lg font-semibold tracking-tight",
  h4: "text-base font-semibold",
  body: "text-sm leading-relaxed",
  bodyLarge: "text-base leading-relaxed",
  label: "text-sm font-medium",
  caption: "text-xs text-muted-foreground",
} as const;

/**
 * Spacing scale — an 8px rhythm expressed through Tailwind's default
 * (4px-unit) scale by convention: always use even-numbered spacing
 * utilities (p-2/4/6/8/12/16...) for layout-level spacing, never odd
 * ones (p-1/3/5) except for fine adjustments inside a single control
 * (e.g. icon gaps). These constants exist for places that need the
 * raw pixel/rem value (non-Tailwind contexts) rather than a class name.
 */
export const spacing = {
  xs: "0.5rem", // 8px
  sm: "1rem", // 16px
  md: "1.5rem", // 24px
  lg: "2rem", // 32px
  xl: "3rem", // 48px
  "2xl": "4rem", // 64px
} as const;

/** Semantic color -> Tailwind class prefix, for status pills/badges/banners. */
export const semanticColor = {
  success: { bg: "bg-success/10", text: "text-success", ring: "ring-success/20" },
  warning: { bg: "bg-warning/15", text: "text-warning-foreground", ring: "ring-warning/30" },
  info: { bg: "bg-info/10", text: "text-info", ring: "ring-info/20" },
  destructive: { bg: "bg-destructive/10", text: "text-destructive", ring: "ring-destructive/20" },
  neutral: { bg: "bg-muted", text: "text-muted-foreground", ring: "ring-border" },
} as const;

export type SemanticColorKey = keyof typeof semanticColor;

/** Standard content container widths — use instead of ad hoc max-w-* per page. */
export const containerWidth = {
  narrow: "max-w-md", // auth forms, single-column flows
  standard: "max-w-3xl", // dashboards, detail views
  wide: "max-w-5xl", // tables, multi-column layouts
} as const;

/**
 * Design tokens Mood-IoT.
 *
 * Single source of truth pour les couleurs, la typographie, les espacements
 * et les radii utilisés dans l'app mobile. Doit rester cohérent avec
 * `frontend/dashboard/src/styles/tokens.css`.
 *
 * Convention :
 *   - `light` / `dark` : palettes complètes pour les 2 modes
 *   - `palette` : couleurs sémantiques (primary, danger, etc.), indépendantes
 *     du mode
 *   - `space` / `radius` / `font` : structurels, indépendants du mode
 */

export const palette = {
  primary50:  "#e1f5fe",
  primary100: "#b3e5fc",
  primary300: "#4fc3f7",
  primary500: "#0288d1",  // brand
  primary700: "#01579b",
  primary900: "#013769",

  success500: "#27ae60",
  warning500: "#f39c12",
  danger500:  "#c0392b",
  neutral500: "#7f8c8d",
} as const;

export const light = {
  bg:         "#f0f7ff",
  surface:    "#ffffff",
  surfaceAlt: "#f4f6fb",
  text:       "#1a1f2e",
  textMuted:  "#5b6478",
  textDim:    "#8a93a6",
  border:     "#dbe2ec",
  borderSoft: "#eef2f8",
  shadow:     "rgba(0, 0, 0, 0.08)",
  overlay:    "rgba(0, 0, 0, 0.45)",
} as const;

export const dark = {
  bg:         "#0d1117",
  surface:    "#161b22",
  surfaceAlt: "#1f2630",
  text:       "#f5f7fa",
  textMuted:  "#9aa3b2",
  textDim:    "#666c7a",
  border:     "#2c3340",
  borderSoft: "#1c222b",
  shadow:     "rgba(0, 0, 0, 0.4)",
  overlay:    "rgba(0, 0, 0, 0.7)",
} as const;

export const space = {
  xs:  4,
  sm:  8,
  md:  12,
  lg:  16,
  xl:  20,
  "2xl": 24,
  "3xl": 32,
  "4xl": 48,
  "5xl": 64,
} as const;

export const radius = {
  sm:  6,
  md:  10,
  lg:  14,
  xl:  20,
  pill: 999,
} as const;

export const font = {
  // Tailles
  size: {
    xs: 11,
    sm: 13,
    base: 15,
    lg: 17,
    xl: 20,
    "2xl": 24,
    "3xl": 28,
    "4xl": 34,
  },
  weight: {
    regular: "400" as const,
    medium:  "500" as const,
    semibold:"600" as const,
    bold:    "700" as const,
  },
  lineHeight: {
    tight:   1.2,
    normal:  1.45,
    relaxed: 1.6,
  },
} as const;

export const duration = {
  fast:   150,
  normal: 250,
  slow:   400,
} as const;

export type ColorScheme = {
  bg: string;
  surface: string;
  surfaceAlt: string;
  text: string;
  textMuted: string;
  textDim: string;
  border: string;
  borderSoft: string;
  shadow: string;
  overlay: string;
};

/** Helper : retourne la palette selon le mode système. */
export function getColors(scheme: "light" | "dark"): ColorScheme {
  return scheme === "dark" ? dark : light;
}

/**
 * ConnX colour tokens: the one source of truth for the UI (through CSS
 * variables, see tailwind.config.ts) and the map layers (MapView imports this
 * file). Contrast and colour-vision checks over these values live in
 * palette.test.ts; the choices are explained in docs/palette.md.
 *
 * A theme is plain data. To add one (e.g. "light"), add its name to THEME_NAMES
 * and an entry to THEMES with the same shape; the tests then check it too.
 *
 * Keep this file free of path aliases and runtime imports: tailwind.config.ts
 * loads it at build time.
 */
import type { Hex } from "./colourMath";

export type { Hex };

/** The five things the map tells apart. */
export const ROLES = ["routeA", "routeB", "overlap", "encounter", "redZone"] as const;
export type Role = (typeof ROLES)[number];

/**
 * How a role is drawn, apart from its colour. Two roles whose colours come
 * close under a colour-vision simulation must use different marks.
 */
export type Mark = "line" | "wide-line" | "dot" | "area";

export interface RoleToken {
  color: Hex;
  /** Text or icons drawn on a fill of `color` (badges, buttons). */
  on: Hex;
  mark: Mark;
  /** Map opacity of the role's main mark (line, dot, or the red spot hit outline). */
  opacity: number;
}

export interface UiTokens {
  bg: Hex;
  panel: Hex;
  panel2: Hex;
  ink: Hex;
  inkDim: Hex;
  /** Placeholders and other quiet text. */
  inkFaint: Hex;
  /** Hairlines; drawn at `borderAlpha`. */
  border: Hex;
  /** Focus rings, selection, active controls. Not a map role. */
  accent: Hex;
  onAccent: Hex;
  /** Error messages and destructive hovers. Not a map role. */
  danger: Hex;
}

/** Colours the basemap style is retinted to (see lib/basemapStyle.ts). */
export interface BasemapTokens {
  background: Hex;
  water: Hex;
  ice: Hex;
  residential: Hex;
  park: Hex;
  building: Hex;
  buildingOutline: Hex;
  path: Hex;
  minorRoad: Hex;
  roadCasing: Hex;
  majorRoad: Hex;
  motorway: Hex;
  aeroArea: Hex;
  rail: Hex;
  railDash: Hex;
  boundaryState: Hex;
  boundaryCountry: Hex;
  label: Hex;
  /** Large places (cities, countries). */
  labelMajor: Hex;
  waterLabel: Hex;
  labelHalo: Hex;
}

/** Opacities of the translucent map fills, per theme (a light basemap needs other values). */
export interface MapOpacity {
  /** Red zone band around Route B. */
  band: number;
  spotFill: number;
  /** Fill of a red spot that Route A enters. */
  spotHitFill: number;
  /** Dashed outline of a red spot. */
  spotOutline: number;
  /** The red spot being drawn or edited. */
  draftFill: number;
  residential: number;
}

export interface Theme {
  roles: Record<Role, RoleToken>;
  ui: UiTokens;
  basemap: BasemapTokens;
  mapOpacity: MapOpacity;
  borderAlpha: number;
}

export const THEME_NAMES = ["dark"] as const;
export type ThemeName = (typeof THEME_NAMES)[number];
export const DEFAULT_THEME: ThemeName = "dark";

const DARK_UI: UiTokens = {
  bg: "#0A0A12",
  panel: "#12131D",
  panel2: "#161826",
  ink: "#ECEEF5",
  inkDim: "#8A90A6",
  inkFaint: "#7E849A",
  border: "#FFFFFF",
  accent: "#5EE6C4",
  onAccent: "#04140F",
  danger: "#FF5A36",
};

const dark: Theme = {
  roles: {
    routeA: { color: "#5EE6C4", on: "#04140F", mark: "line", opacity: 0.95 },
    routeB: { color: "#B98CFF", on: "#160A2E", mark: "line", opacity: 0.8 },
    overlap: { color: "#F64DA6", on: "#22041A", mark: "wide-line", opacity: 1 },
    encounter: { color: "#F5C24B", on: "#1A1405", mark: "dot", opacity: 1 },
    redZone: { color: "#FF5A36", on: "#1F0702", mark: "area", opacity: 0.95 },
  },
  ui: DARK_UI,
  basemap: {
    background: DARK_UI.bg,
    water: "#0E1626",
    ice: DARK_UI.panel,
    residential: "#0E0F19",
    park: "#0F1A1B",
    building: "#11121D",
    buildingOutline: "#1A1C2C",
    path: "#23263A",
    minorRoad: "#1D2033",
    roadCasing: DARK_UI.bg,
    majorRoad: "#272A42",
    motorway: "#2F3354",
    aeroArea: DARK_UI.panel2,
    rail: "#1E2134",
    railDash: DARK_UI.bg,
    boundaryState: "#2A2D44",
    boundaryCountry: "#33375A",
    label: DARK_UI.inkDim,
    labelMajor: DARK_UI.ink,
    waterLabel: "#6E7EA6",
    labelHalo: DARK_UI.bg,
  },
  mapOpacity: { band: 0.16, spotFill: 0.1, spotHitFill: 0.28, spotOutline: 0.85, draftFill: 0.2, residential: 0.6 },
  borderAlpha: 0.08,
};

export const THEMES: Record<ThemeName, Theme> = { dark };

// ---- CSS variables, for Tailwind and globals.css ----------------------------

const kebab = (name: string) => name.replace(/([a-z])([A-Z0-9])/g, "$1-$2").toLowerCase();

function channels(hex: Hex): string {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");
}

/** Token name (kebab-case) -> colour, for every colour the UI uses. */
function uiColours(theme: Theme): Record<string, Hex> {
  const out: Record<string, Hex> = {};
  for (const [name, value] of Object.entries(theme.ui)) out[kebab(name)] = value;
  for (const role of ROLES) {
    out[kebab(role)] = theme.roles[role].color;
    out[`on-${kebab(role)}`] = theme.roles[role].on;
  }
  return out;
}

/**
 * The CSS custom properties for a theme: `--c-<token>` as "R G B" channels
 * (so Tailwind's `/opacity` modifiers work), plus `--a-border`.
 */
export function cssVariables(theme: Theme): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const [name, hex] of Object.entries(uiColours(theme))) vars[`--c-${name}`] = channels(hex);
  vars["--a-border"] = String(theme.borderAlpha);
  return vars;
}

/** Tailwind `colors`: every token as a CSS variable, so a theme switch needs no rebuild. */
export function tailwindColors(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of Object.keys(uiColours(THEMES[DEFAULT_THEME]))) {
    out[name] = `rgb(var(--c-${name}) / <alpha-value>)`;
  }
  out["border"] = "rgb(var(--c-border) / var(--a-border))";
  return out;
}

/**
 * The stylesheet that defines every theme's variables. The default theme is
 * also the `:root`; each theme can be forced with `<html data-theme="name">`.
 */
export function themeCss(): string {
  const block = (vars: Record<string, string>) =>
    Object.entries(vars)
      .map(([k, v]) => `${k}:${v};`)
      .join("");
  const rules = THEME_NAMES.map((name) => {
    const selector = name === DEFAULT_THEME ? `:root,[data-theme="${name}"]` : `[data-theme="${name}"]`;
    return `${selector}{${block(cssVariables(THEMES[name]))}}`;
  });
  return rules.join("\n");
}

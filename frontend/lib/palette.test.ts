/**
 * The palette's contrast and colour-vision guarantees, checked over the tokens
 * so they keep holding when a colour changes or a theme is added. Every check
 * runs for every theme in THEMES. Thresholds and their reasons: docs/palette.md.
 */
import { describe, expect, it } from "vitest";
import { blend, chroma, contrast, deltaE, isHex } from "./colourMath";
import {
  ROLES,
  THEMES,
  THEME_NAMES,
  cssVariables,
  tailwindColors,
  themeCss,
  type Role,
  type Theme,
} from "./palette";

const TEXT_MIN = 4.5; // WCAG 2 AA, normal-size text
const MARK_MIN = 3; // WCAG 2 non-text contrast, for map marks and UI graphics
const NORMAL_MIN = 15; // OKLab dE x100, any two roles, full colour vision
const CVD_TARGET = 8; // OKLab dE x100 under simulation: no second cue needed
const CVD_FLOOR = 6; // below the target and above this only with a different mark
const CHROMA_MIN = 0.1; // below this a hue reads as grey

const pairs = <T,>(xs: readonly T[]) => xs.flatMap((a, i) => xs.slice(i + 1).map((b) => [a, b] as const));

// Everything a role is drawn over on the map.
function mapSurfaces(t: Theme): Record<string, string> {
  const m = t.basemap;
  return {
    background: m.background,
    water: m.water,
    park: m.park,
    building: m.building,
    path: m.path,
    minorRoad: m.minorRoad,
    majorRoad: m.majorRoad,
    motorway: m.motorway,
    redZoneBand: blend(t.roles.redZone.color, t.mapOpacity.band, m.background),
    redSpotHit: blend(t.roles.redZone.color, t.mapOpacity.spotHitFill, m.background),
  };
}

describe.each(THEME_NAMES)("%s theme", (name) => {
  const t = THEMES[name];
  const ui = t.ui;
  const panels = { bg: ui.bg, panel: ui.panel, panel2: ui.panel2 };

  it("has a token for every role", () => {
    expect(Object.keys(t.roles).sort()).toEqual([...ROLES].sort());
  });

  it("uses only #RRGGBB values", () => {
    const values = [
      ...Object.values(ui),
      ...Object.values(t.basemap),
      ...ROLES.flatMap((r) => [t.roles[r].color, t.roles[r].on]),
    ];
    for (const v of values) expect(isHex(v), v).toBe(true);
  });

  describe("text contrast", () => {
    const textTokens = {
      ink: ui.ink,
      inkDim: ui.inkDim,
      inkFaint: ui.inkFaint,
      accent: ui.accent,
      danger: ui.danger,
      // Role colours are also used as text (labels, values, the encounter gap on the map).
      ...Object.fromEntries(ROLES.map((r) => [r, t.roles[r].color])),
    };
    for (const [textName, text] of Object.entries(textTokens)) {
      for (const [surfaceName, surface] of Object.entries(panels)) {
        it(`${textName} on ${surfaceName} >= ${TEXT_MIN}:1`, () => {
          expect(contrast(text, surface)).toBeGreaterThanOrEqual(TEXT_MIN);
        });
      }
    }

    it.each(ROLES)(`text on a %s fill >= ${TEXT_MIN}:1`, (r) => {
      expect(contrast(t.roles[r].on, t.roles[r].color)).toBeGreaterThanOrEqual(TEXT_MIN);
    });

    it(`text on an accent fill >= ${TEXT_MIN}:1`, () => {
      expect(contrast(ui.onAccent, ui.accent)).toBeGreaterThanOrEqual(TEXT_MIN);
    });

    it(`basemap labels on their halo >= ${TEXT_MIN}:1`, () => {
      const m = t.basemap;
      for (const label of [m.label, m.labelMajor, m.waterLabel]) {
        expect(contrast(label, m.labelHalo), label).toBeGreaterThanOrEqual(TEXT_MIN);
      }
    });
  });

  describe("map marks", () => {
    const surfaces = mapSurfaces(t);
    // Lines and dots. The red zone is checked through its outline below.
    const marks: Role[] = ["routeA", "routeB", "overlap", "encounter"];
    for (const r of marks) {
      for (const [surfaceName, surface] of Object.entries(surfaces)) {
        it(`${r} on ${surfaceName} >= ${MARK_MIN}:1`, () => {
          // As drawn: at the role's map opacity over that surface.
          const drawn = blend(t.roles[r].color, t.roles[r].opacity, surface);
          expect(contrast(drawn, surface)).toBeGreaterThanOrEqual(MARK_MIN);
        });
      }
    }

    it(`red spot outlines >= ${MARK_MIN}:1 on the background and roads`, () => {
      const { background, path, minorRoad, majorRoad, motorway } = surfaces;
      for (const surface of [background, path, minorRoad, majorRoad, motorway]) {
        const outline = blend(t.roles.redZone.color, t.mapOpacity.spotOutline, surface);
        const hitOutline = blend(t.roles.redZone.color, t.roles.redZone.opacity, surface);
        expect(contrast(outline, surface), surface).toBeGreaterThanOrEqual(MARK_MIN);
        expect(contrast(hitOutline, surface), surface).toBeGreaterThanOrEqual(MARK_MIN);
      }
    });

    it(`the selected-card ring and focus outline (accent) >= ${MARK_MIN}:1 on the panels`, () => {
      for (const surface of Object.values(panels)) {
        expect(contrast(ui.accent, surface)).toBeGreaterThanOrEqual(MARK_MIN);
      }
    });
  });

  describe("roles stay apart", () => {
    it.each(ROLES)(`%s has chroma >= ${CHROMA_MIN} (reads as a colour, not grey)`, (r) => {
      expect(chroma(t.roles[r].color)).toBeGreaterThanOrEqual(CHROMA_MIN);
    });

    // All pairs, not just neighbours: on a map any two roles can touch.
    for (const [a, b] of pairs(ROLES)) {
      it(`${a} vs ${b}: normal vision dE >= ${NORMAL_MIN}`, () => {
        expect(deltaE(t.roles[a].color, t.roles[b].color)).toBeGreaterThanOrEqual(NORMAL_MIN);
      });

      // Protan and deutan (the common deficiencies, which the thresholds are
      // calibrated to): at least the floor, and below the target only with a
      // second cue. Tritan is rare and uncalibrated here, so any pair below the
      // target there just needs the second cue.
      it(`${a} vs ${b}: separate under protan and deutan simulation, or carry a second cue`, () => {
        const ca = t.roles[a].color;
        const cb = t.roles[b].color;
        const worst = Math.min(deltaE(ca, cb, "protan"), deltaE(ca, cb, "deutan"));
        expect(worst).toBeGreaterThanOrEqual(CVD_FLOOR);
        if (worst < CVD_TARGET) {
          expect(t.roles[a].mark, `dE ${worst.toFixed(1)}: needs a different mark`).not.toBe(t.roles[b].mark);
        }
      });

      it(`${a} vs ${b}: separate under tritan simulation, or carry a second cue`, () => {
        const d = deltaE(t.roles[a].color, t.roles[b].color, "tritan");
        if (d < CVD_TARGET) {
          expect(t.roles[a].mark, `dE ${d.toFixed(1)}: needs a different mark`).not.toBe(t.roles[b].mark);
        }
      });
    }
  });

  describe("CSS variables", () => {
    const vars = cssVariables(t);

    it("define every colour Tailwind refers to, as rgb channels", () => {
      for (const value of Object.values(tailwindColors())) {
        const used = value.match(/--[a-z0-9-]+/g) ?? [];
        for (const v of used) expect(vars[v], v).toMatch(/^(\d{1,3} \d{1,3} \d{1,3}|0?\.\d+|1|0)$/);
      }
    });

    it("carry the role colours", () => {
      expect(vars["--c-route-a"]).toBeDefined();
      expect(vars["--c-route-b"]).toBeDefined();
      expect(vars["--c-overlap"]).toBeDefined();
      expect(vars["--c-encounter"]).toBeDefined();
      expect(vars["--c-red-zone"]).toBeDefined();
      expect(vars["--c-on-encounter"]).toBeDefined();
    });
  });
});

describe("themeCss", () => {
  it("makes the default theme the :root and scopes every theme to [data-theme]", () => {
    const css = themeCss();
    expect(css).toContain(":root,");
    expect(css).toContain("--c-route-a:94 230 196;");
    for (const name of THEME_NAMES) expect(css).toContain(`[data-theme="${name}"]{`);
  });
});

describe("tailwindColors", () => {
  it("exposes each role and UI token through a CSS variable, so themes swap without a rebuild", () => {
    const colors = tailwindColors();
    expect(colors["route-a"]).toBe("rgb(var(--c-route-a) / <alpha-value>)");
    expect(colors["red-zone"]).toBe("rgb(var(--c-red-zone) / <alpha-value>)");
    expect(colors["panel-2"]).toBe("rgb(var(--c-panel-2) / <alpha-value>)");
    expect(colors["border"]).toBe("rgb(var(--c-border) / var(--a-border))");
  });

  it("keeps the same variable names in every theme", () => {
    const names = THEME_NAMES.map((n) => Object.keys(cssVariables(THEMES[n])).sort().join(","));
    expect(new Set(names).size).toBe(1);
  });
});

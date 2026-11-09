/**
 * Colour measurements used to check the palette (see docs/palette.md and
 * lib/palette.test.ts). Ported from the dataviz method's validate_palette.js so
 * the thresholds there apply unchanged:
 *
 * - contrast: WCAG 2 contrast ratio.
 * - deltaE: Euclidean distance in OKLab, x100.
 * - Colour-vision deficiency: Machado, Oliveira & Fernandes (2009) at severity
 *   1.0, applied in linear RGB. The CVD thresholds are calibrated to this model.
 */

export type Hex = `#${string}`;
export type Deficiency = "protan" | "deutan" | "tritan";

const HEX_RE = /^#[0-9a-fA-F]{6}$/;

export function isHex(value: string): value is Hex {
  return HEX_RE.test(value);
}

function srgb(hex: string): [number, number, number] {
  if (!isHex(hex)) throw new Error(`expected #RRGGBB, got ${JSON.stringify(hex)}`);
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];
}

const toLinear = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const linearRgb = (hex: string) => srgb(hex).map(toLinear) as [number, number, number];

/** "94 230 196": the channel form a CSS `rgb(var(--x) / <alpha>)` variable needs. */
export function rgbChannels(hex: string): string {
  return srgb(hex)
    .map((c) => Math.round(c * 255))
    .join(" ");
}

function luminance(hex: string): number {
  const [r, g, b] = linearRgb(hex);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2 contrast ratio, 1 to 21. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `color` at `opacity` over an opaque `background`, blended in sRGB as browsers and MapLibre do. */
export function blend(color: string, opacity: number, background: string): Hex {
  const fg = srgb(color);
  const bg = srgb(background);
  return ("#" +
    fg
      .map((c, i) => Math.round((c * opacity + bg[i] * (1 - opacity)) * 255))
      .map((v) => v.toString(16).padStart(2, "0"))
      .join("")
      .toUpperCase()) as Hex;
}

type Matrix = [[number, number, number], [number, number, number], [number, number, number]];
const MACHADO: Record<Deficiency, Matrix> = {
  protan: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deutan: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  tritan: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};

function simulate(hex: string, kind: Deficiency): [number, number, number] {
  const [r, g, b] = linearRgb(hex);
  const clamp = (c: number) => Math.max(0, Math.min(1, c));
  return MACHADO[kind].map((row) => clamp(row[0] * r + row[1] * g + row[2] * b)) as [number, number, number];
}

function oklab([r, g, b]: [number, number, number]): [number, number, number] {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** OKLCH chroma. Below ~0.10 a colour reads as grey. */
export function chroma(hex: string): number {
  const [, a, b] = oklab(linearRgb(hex));
  return Math.hypot(a, b);
}

/** OKLab distance x100 between two colours, optionally as seen with a colour-vision deficiency. */
export function deltaE(a: string, b: string, kind?: Deficiency): number {
  const p = oklab(kind ? simulate(a, kind) : linearRgb(a));
  const q = oklab(kind ? simulate(b, kind) : linearRgb(b));
  return 100 * Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
}

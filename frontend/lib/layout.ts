// Layout helpers for the responsive planner.
//
// Breakpoint: Tailwind's `md` (768 px). At and above it the planner keeps the
// side panel; below it the panel becomes a bottom sheet under the map. Keep
// DESKTOP_MEDIA_QUERY in step with the `md:` classes in the planner.

export const DESKTOP_MIN_WIDTH_PX = 768;
export const DESKTOP_MEDIA_QUERY = `(min-width: ${DESKTOP_MIN_WIDTH_PX}px)`;

/** True when the side panel layout is showing (browser only). */
export function isDesktopLayout(): boolean {
  return typeof window !== "undefined" && window.matchMedia(DESKTOP_MEDIA_QUERY).matches;
}

/** "overlay": a card floating over the bottom of the map (desktop). "inline": in the bottom sheet (phones). */
export type CardPlacement = "overlay" | "inline";

export interface Padding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/**
 * Shrinks map fit padding so that at least `minFree` of each dimension is
 * left for the content. MapLibre does nothing at all when the padding is
 * larger than the canvas, which happens on a phone's short map.
 */
export function fitPadding(width: number, height: number, desired: Padding, minFree = 0.4): Padding {
  const sx = shrink(desired.left + desired.right, width, minFree);
  const sy = shrink(desired.top + desired.bottom, height, minFree);
  return {
    top: desired.top * sy,
    right: desired.right * sx,
    bottom: desired.bottom * sy,
    left: desired.left * sx,
  };
}

function shrink(total: number, size: number, minFree: number): number {
  const max = Math.max(0, size * (1 - minFree));
  return total > max && total > 0 ? max / total : 1;
}

export interface DropdownPlacement {
  /** Viewport y of the list's top edge (placement "below") or bottom edge ("above"). */
  y: number;
  left: number;
  width: number;
  maxHeight: number;
  side: "below" | "above";
}

/**
 * Where to put a search dropdown for an input at `anchor` (viewport coords).
 * Opens below unless the visible area (`view`, e.g. above an on-screen
 * keyboard or the bottom of the screen) has more room above the input.
 */
export function dropdownPlacement(
  anchor: { top: number; bottom: number; left: number; width: number },
  view: { top: number; bottom: number },
  { gap = 4, margin = 8, maxHeight = 208 } = {}
): DropdownPlacement {
  const below = view.bottom - anchor.bottom - gap - margin;
  const above = anchor.top - view.top - gap - margin;
  const side = below >= maxHeight || below >= above ? "below" : "above";
  const room = side === "below" ? below : above;
  return {
    y: side === "below" ? anchor.bottom + gap : anchor.top - gap,
    left: anchor.left,
    width: anchor.width,
    // Never collapse to nothing: a short list that scrolls beats no list.
    maxHeight: Math.max(96, Math.min(maxHeight, room)),
    side,
  };
}

/**
 * One line for the collapsed bottom sheet's handle bar: the result of the
 * last comparison, so a phone user can read it without opening the sheet.
 */
export function sheetSummary(result: {
  routeCount: number;
  overlapKm: number | null;
  /** Close passes of the selected route; null when there is no route to avoid. */
  encounterCount: number | null;
}): string {
  if (result.routeCount === 0 || result.overlapKm === null) return "Plan your route";
  const parts = [`${result.routeCount} route${result.routeCount === 1 ? "" : "s"}`, `${result.overlapKm} km overlap`];
  if (result.encounterCount !== null) {
    parts.push(`${result.encounterCount} close pass${result.encounterCount === 1 ? "" : "es"}`);
  }
  return parts.join(" · ");
}

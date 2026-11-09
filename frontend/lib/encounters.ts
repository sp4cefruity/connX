import type { Encounter, LonLat } from "@/lib/types";

export interface ZoomTarget {
  /** The points to bring into view. */
  points: LonLat[];
  /** Changes on every request, so asking for the same encounter twice still zooms. */
  key: number;
}

/** The encounter's whole stretch plus its marker, so both are on screen. */
export function encounterZoomPoints(e: Encounter): LonLat[] {
  return [...e.geometry, e.location];
}

/** "55 m" up to 999 m, then "1.2 km". Picks the unit before rounding, so 999.7 m is not "1000 m". */
export function formatGap(metres: number): string {
  return metres < 999.5 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(1)} km`;
}

/** Distance along Route A where the encounter's closest point sits, e.g. "0.8 km". */
export function formatAlong(e: Encounter, routeDistanceKm: number): string {
  return `${(e.position_fraction * routeDistanceKm).toFixed(1)} km`;
}

/** Card summary: "No close passes", "1 close pass · 60 m", "2 close passes · nearest 60 m". */
export function closePassSummary(encounters: Encounter[]): string {
  if (encounters.length === 0) return "No close passes";
  const nearest = formatGap(Math.min(...encounters.map((e) => e.min_gap_m)));
  if (encounters.length === 1) return `1 close pass · ${nearest}`;
  return `${encounters.length} close passes · nearest ${nearest}`;
}

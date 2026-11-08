import type { Encounter, LonLat, ScoredRoute } from "@/lib/types";

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

/**
 * Same trip, different server response: identify a route by what it is, not
 * by its position in the list (ranking can change between requests).
 */
function routeKey(r: ScoredRoute): string {
  const g = r.route.geometry;
  const first = g[0];
  const last = g[g.length - 1];
  return [r.route.distance_km, r.route.duration_min, g.length, first?.lon, first?.lat, last?.lon, last?.lat].join("|");
}

/**
 * Carry a refreshed response's encounters onto the routes already on screen.
 * The danger-distance slider changes encounters but nothing else, and keeping
 * the route objects themselves untouched stops the map from re-fitting.
 *
 * Returns null when any route on screen is missing from the response (the
 * candidate set changed), so the caller can replace the routes instead of
 * leaving encounters computed for the old danger distance.
 */
export function withRefreshedEncounters(current: ScoredRoute[], fresh: ScoredRoute[]): ScoredRoute[] | null {
  const byKey = new Map(fresh.map((r) => [routeKey(r), r.encounters]));
  const out: ScoredRoute[] = [];
  for (const r of current) {
    const encounters = byKey.get(routeKey(r));
    if (!encounters) return null;
    out.push({ ...r, encounters });
  }
  return out;
}

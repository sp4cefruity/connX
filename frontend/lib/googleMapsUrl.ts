import type { LonLat, RouteResult, TravelMode } from "@/lib/types";

/** Most via points Google Maps accepts: 9 on desktop, 3 on mobile. */
export const MAX_WAYPOINTS_DESKTOP = 9;
export const MAX_WAYPOINTS_MOBILE = 3;

const TRAVEL_MODE: Record<TravelMode, string> = {
  driving: "driving",
  walking: "walking",
  cycling: "bicycling",
};

const EARTH_RADIUS_M = 6_371_000;
const toRad = (deg: number) => (deg * Math.PI) / 180;

function haversineM(a: LonLat, b: LonLat): number {
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * `count` points evenly spaced by distance along the line, excluding its ends.
 * Each lies on the line itself (interpolated within a segment), so Google is
 * steered along the same road rather than to an off-route spot.
 */
export function evenWaypoints(line: LonLat[], count: number): LonLat[] {
  if (count <= 0 || line.length < 2) return [];
  const cumulative = [0];
  for (let i = 1; i < line.length; i++) cumulative.push(cumulative[i - 1] + haversineM(line[i - 1], line[i]));
  const total = cumulative[cumulative.length - 1];
  if (total === 0) return [];

  const points: LonLat[] = [];
  let seg = 1;
  for (let k = 1; k <= count; k++) {
    const target = (total * k) / (count + 1);
    while (seg < line.length - 1 && cumulative[seg] < target) seg++;
    const span = cumulative[seg] - cumulative[seg - 1];
    const t = span === 0 ? 0 : (target - cumulative[seg - 1]) / span;
    const a = line[seg - 1];
    const b = line[seg];
    points.push({ lon: a.lon + (b.lon - a.lon) * t, lat: a.lat + (b.lat - a.lat) * t });
  }
  return points;
}

const coord = (p: LonLat) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`;

/**
 * Google Maps directions URL for one route: its start, end and evenly spaced
 * via points. Returns null when the route has fewer than two points.
 */
export function googleMapsUrl(route: RouteResult, maxWaypoints: number): string | null {
  const line = route.geometry;
  if (line.length < 2) return null;
  const params = new URLSearchParams({
    api: "1",
    origin: coord(line[0]),
    destination: coord(line[line.length - 1]),
    travelmode: TRAVEL_MODE[route.mode],
  });
  const via = evenWaypoints(line, maxWaypoints).map(coord);
  if (via.length > 0) params.set("waypoints", via.join("|"));
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

/** Narrow viewport or a phone/tablet user agent; browser only. */
export function isMobileClient(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 639px)").matches || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

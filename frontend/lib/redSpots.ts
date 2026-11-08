import type { LonLat } from "./types";

// Red spot radius limits. Mirrors MIN_RADIUS_M / MAX_RADIUS_M in
// backend/app/schemas.py, which is the authority (the API rejects anything outside).
export const MIN_RADIUS_M = 50;
export const MAX_RADIUS_M = 2000;
export const DEFAULT_RADIUS_M = 150;
export const RADIUS_STEP_M = 10;

const METERS_PER_DEG_LAT = 111_320;

/** Snap to the slider step and keep inside the allowed range. */
export function clampRadius(meters: number): number {
  if (!Number.isFinite(meters)) return DEFAULT_RADIUS_M;
  const snapped = Math.round(meters / RADIUS_STEP_M) * RADIUS_STEP_M;
  return Math.min(MAX_RADIUS_M, Math.max(MIN_RADIUS_M, snapped));
}

export function formatRadius(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1).replace(/\.0$/, "")} km`;
}

/** Distance in metres between two nearby points (same projection as the backend). */
export function metersBetween(a: LonLat, b: LonLat): number {
  const cosLat = Math.cos((((a.lat + b.lat) / 2) * Math.PI) / 180);
  const dx = (b.lon - a.lon) * METERS_PER_DEG_LAT * cosLat;
  const dy = (b.lat - a.lat) * METERS_PER_DEG_LAT;
  return Math.hypot(dx, dy);
}

/** The point `meters` due east of `center`. */
export function offsetEast(center: LonLat, meters: number): LonLat {
  const cosLat = Math.cos((center.lat * Math.PI) / 180);
  return { lon: center.lon + meters / (METERS_PER_DEG_LAT * cosLat), lat: center.lat };
}

/** Closed ring of [lon, lat] vertices approximating a circle of `radiusM` metres. */
export function circleRing(center: LonLat, radiusM: number, steps = 64): [number, number][] {
  const cosLat = Math.cos((center.lat * Math.PI) / 180);
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    ring.push([
      center.lon + (radiusM * Math.cos(angle)) / (METERS_PER_DEG_LAT * cosLat),
      center.lat + (radiusM * Math.sin(angle)) / METERS_PER_DEG_LAT,
    ]);
  }
  return ring;
}

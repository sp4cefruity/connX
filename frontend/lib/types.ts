export type TravelMode = "driving" | "walking" | "cycling";

/** Danger distance bounds in metres (ADR 0001); must match the backend. */
export const DANGER_DISTANCE_MIN_M = 50;
export const DANGER_DISTANCE_MAX_M = 1000;
export const DANGER_DISTANCE_DEFAULT_M = 200;

export interface LonLat {
  lon: number;
  lat: number;
}

export interface GeocodeResult {
  label: string;
  address: string | null;
  lon: number;
  lat: number;
}

export interface RouteResult {
  distance_km: number;
  duration_min: number;
  geometry: LonLat[];
  mode: TravelMode;
}

export interface OverlapSegment {
  type: "crossing" | "shared_segment";
  distance_m: number;
  geometry: LonLat[];
  start_fraction: number;
  end_fraction: number;
}

export interface OverlapResult {
  distance_km: number;
  percentage: number;
  duration_min: number;
  segments: OverlapSegment[];
}

/** A stretch of Route A within the danger distance of Route B that is not Overlap. */
export interface Encounter {
  /** Closest point to Route B: where the marker goes. */
  location: LonLat;
  min_gap_m: number;
  /** 0..1 along Route A, at `location`. */
  position_fraction: number;
  start_fraction: number;
  end_fraction: number;
  distance_m: number;
  /** The stretch itself, used to zoom to it. */
  geometry: LonLat[];
}

export interface RedSpot {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius_m: number;
  type: string | null;
  temporary: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface RedSpotHit {
  red_spot: RedSpot;
  intersects: boolean;
  min_distance_m: number;
}

export interface RouteScoreBreakdown {
  time_penalty: number;
  overlap_penalty: number;
  /** Close passes with Route B, weighted by how close each one gets. */
  encounter_penalty: number;
  red_zone_penalty: number;
  distance_penalty: number;
  total: number;
}

export interface ScoredRoute {
  tier: "recommended" | "alternative" | "fastest";
  route: RouteResult;
  overlap: OverlapResult;
  encounters: Encounter[];
  red_spot_hits: RedSpotHit[];
  score: RouteScoreBreakdown;
  explanation: string[];
}

/** What the map and side panel need about one Route A, compared or recommended. */
export type RouteView = Pick<ScoredRoute, "route" | "overlap" | "encounters" | "red_spot_hits">;

/** The comparison view's Route A, together with the Route B it is compared against. */
export type ComparisonView = RouteView & { comparison_route: RouteResult };

/** GeoJSON Polygon / MultiPolygon geometry, coordinates in [lon, lat]. */
export type RedZoneBand =
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

export interface RecommendResponse {
  routes: ScoredRoute[];
  recommended_index: number;
  comparison_route: RouteResult | null;
  /** Route B buffered by the danger distance; null when there is no Route B. */
  red_zone_band: RedZoneBand | null;
}

export interface CompareResponse {
  primary_route: RouteResult;
  comparison_route: RouteResult;
  overlap: OverlapResult;
  red_zone_band: RedZoneBand | null;
  encounters: Encounter[];
  red_spots: RedSpotHit[];
}

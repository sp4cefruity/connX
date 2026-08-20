export type TravelMode = "driving" | "walking" | "cycling";
export type Sensitivity = "low" | "medium" | "high";

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
  red_zone_penalty: number;
  distance_penalty: number;
  total: number;
}

export interface ScoredRoute {
  tier: "recommended" | "alternative" | "fastest";
  route: RouteResult;
  overlap: OverlapResult;
  red_spot_hits: RedSpotHit[];
  score: RouteScoreBreakdown;
  explanation: string[];
}

export interface RecommendResponse {
  routes: ScoredRoute[];
  recommended_index: number;
  comparison_route: RouteResult | null;
}

export interface CompareResponse {
  primary_route: RouteResult;
  comparison_route: RouteResult;
  overlap: OverlapResult;
  red_spots: RedSpotHit[];
}

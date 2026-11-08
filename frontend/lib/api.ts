import type {
  CompareResponse,
  GeocodeResult,
  LonLat,
  RecommendResponse,
  RedSpot,
  TravelMode,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include", // send the anonymous device cookie
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

/** Backend answers 503 when every geocoding provider failed or timed out. */
export function isSearchSlowError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 503;
}

export async function geocode(
  query: string,
  opts?: { signal?: AbortSignal; bias?: LonLat | null }
): Promise<GeocodeResult[]> {
  if (!query.trim()) return [];
  let url = `/api/geocode?q=${encodeURIComponent(query)}`;
  // Map centre biases results toward what the user is looking at.
  if (opts?.bias) url += `&lat=${opts.bias.lat.toFixed(3)}&lon=${opts.bias.lon.toFixed(3)}`;
  return request(url, { signal: opts?.signal });
}

export async function compareRoutes(params: {
  primaryStart: LonLat;
  primaryEnd: LonLat;
  comparisonStart: LonLat;
  comparisonEnd: LonLat;
  mode: TravelMode;
  dangerDistanceM: number;
}): Promise<CompareResponse> {
  return request("/api/routes/compare", {
    method: "POST",
    body: JSON.stringify({
      primary_start: params.primaryStart,
      primary_end: params.primaryEnd,
      comparison_start: params.comparisonStart,
      comparison_end: params.comparisonEnd,
      mode: params.mode,
      danger_distance_m: params.dangerDistanceM,
      include_red_spots: true,
    }),
  });
}

export async function recommendRoutes(params: {
  primaryStart: LonLat;
  primaryEnd: LonLat;
  comparisonStart?: LonLat;
  comparisonEnd?: LonLat;
  mode: TravelMode;
  dangerDistanceM: number;
  avoidOverlap: boolean;
  avoidRedSpots: boolean;
}): Promise<RecommendResponse> {
  return request("/api/routes/recommend", {
    method: "POST",
    body: JSON.stringify({
      primary_start: params.primaryStart,
      primary_end: params.primaryEnd,
      comparison_start: params.comparisonStart ?? null,
      comparison_end: params.comparisonEnd ?? null,
      mode: params.mode,
      danger_distance_m: params.dangerDistanceM,
      avoid_overlap: params.avoidOverlap,
      avoid_red_spots: params.avoidRedSpots,
      alternatives_count: 3,
    }),
  });
}

export async function listRedSpots(): Promise<RedSpot[]> {
  return request("/api/red-spots");
}

export async function createRedSpot(payload: {
  name: string;
  latitude: number;
  longitude: number;
  radius_m: number;
  type?: string;
}): Promise<RedSpot> {
  return request("/api/red-spots", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateRedSpot(
  id: string,
  patch: Partial<{ name: string; latitude: number; longitude: number; radius_m: number }>
): Promise<RedSpot> {
  return request(`/api/red-spots/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}

export async function deleteRedSpot(id: string): Promise<void> {
  return request(`/api/red-spots/${id}`, { method: "DELETE" });
}

export { ApiError };

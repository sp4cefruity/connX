import { describe, expect, it } from "vitest";
import { evenWaypoints, googleMapsUrl } from "./googleMapsUrl";
import type { LonLat, RouteResult, TravelMode } from "./types";

// A straight line along the equator: 0.1 degree of longitude per step.
const line: LonLat[] = Array.from({ length: 11 }, (_, i) => ({ lon: i * 0.1, lat: 0 }));
const route = (mode: TravelMode, geometry = line): RouteResult => ({
  distance_km: 1,
  duration_min: 1,
  geometry,
  mode,
});

describe("evenWaypoints", () => {
  it("spaces points evenly by distance and keeps them on the line", () => {
    const pts = evenWaypoints(line, 4);
    expect(pts.map((p) => +p.lon.toFixed(6))).toEqual([0.2, 0.4, 0.6, 0.8]);
    pts.forEach((p) => expect(p.lat).toBe(0));
  });

  it("weights by distance, not vertex count", () => {
    const uneven: LonLat[] = [
      { lon: 0, lat: 0 },
      { lon: 0.01, lat: 0 },
      { lon: 1, lat: 0 },
    ];
    const [mid] = evenWaypoints(uneven, 1);
    expect(mid.lon).toBeCloseTo(0.5, 6);
  });

  it("returns nothing for zero count or degenerate lines", () => {
    expect(evenWaypoints(line, 0)).toEqual([]);
    expect(evenWaypoints([line[0]], 3)).toEqual([]);
    expect(evenWaypoints([line[0], line[0]], 3)).toEqual([]);
  });
});

describe("googleMapsUrl", () => {
  it("builds origin, destination, mode and piped waypoints as lat,lon", () => {
    const url = new URL(googleMapsUrl(route("driving"), 2)!);
    expect(url.origin + url.pathname).toBe("https://www.google.com/maps/dir/");
    expect(url.searchParams.get("api")).toBe("1");
    expect(url.searchParams.get("origin")).toBe("0.000000,0.000000");
    expect(url.searchParams.get("destination")).toBe("0.000000,1.000000");
    expect(url.searchParams.get("travelmode")).toBe("driving");
    expect(url.searchParams.get("waypoints")!.split("|")).toHaveLength(2);
    expect(url.search).toContain("%7C");
  });

  it("maps connX modes to Google travel modes", () => {
    const mode = (m: TravelMode) => new URL(googleMapsUrl(route(m), 0)!).searchParams.get("travelmode");
    expect(mode("walking")).toBe("walking");
    expect(mode("cycling")).toBe("bicycling");
  });

  it("honours the waypoint cap and omits the parameter at zero", () => {
    const count = (n: number) => new URL(googleMapsUrl(route("driving"), n)!).searchParams.get("waypoints");
    expect(count(9)!.split("|")).toHaveLength(9);
    expect(count(3)!.split("|")).toHaveLength(3);
    expect(count(0)).toBeNull();
  });

  it("returns null for a route without a line", () => {
    expect(googleMapsUrl(route("driving", [line[0]]), 3)).toBeNull();
  });
});

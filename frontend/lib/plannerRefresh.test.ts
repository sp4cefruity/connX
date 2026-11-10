import { describe, expect, it } from "vitest";
import { comparisonFrom, refreshComparison } from "./plannerRefresh";
import type { CompareResponse, RouteResult } from "./types";

function route(distance_km: number, duration_min: number): RouteResult {
  return {
    distance_km,
    duration_min,
    mode: "driving",
    geometry: [
      { lon: 0, lat: 0 },
      { lon: 1, lat: 1 },
    ],
  };
}

function response(overrides: Partial<CompareResponse> = {}): CompareResponse {
  return {
    primary_route: route(3.1, 12),
    comparison_route: route(3.4, 14),
    overlap: { distance_km: 0, percentage: 0, duration_min: 0, segments: [] },
    red_zone_band: null,
    encounters: [],
    red_spots: [],
    ...overrides,
  };
}

describe("comparisonFrom", () => {
  it("carries Route B on the comparison view", () => {
    const fresh = response();
    expect(comparisonFrom(fresh).comparison_route).toBe(fresh.comparison_route);
  });
});

describe("refreshComparison", () => {
  it("keeps the on-screen Route A and Route B objects when they are unchanged", () => {
    const current = comparisonFrom(response());
    const next = refreshComparison(current, response());
    expect(next.route).toBe(current.route);
    expect(next.comparison_route).toBe(current.comparison_route);
  });

  it("takes the fresh Route B when it changed", () => {
    const current = comparisonFrom(response());
    const fresh = response({ comparison_route: route(5, 20) });
    expect(refreshComparison(current, fresh).comparison_route).toBe(fresh.comparison_route);
  });

  it("takes the fresh overlap when Route B changed, since overlap compares A with B", () => {
    const current = comparisonFrom(response());
    const fresh = response({
      comparison_route: route(5, 20),
      overlap: { distance_km: 1, percentage: 30, duration_min: 4, segments: [] },
    });
    expect(refreshComparison(current, fresh).overlap).toBe(fresh.overlap);
  });

  it("returns the fresh view wholesale when Route A changed", () => {
    const current = comparisonFrom(response());
    const fresh = response({ primary_route: route(9, 30) });
    const next = refreshComparison(current, fresh);
    expect(next.route).toBe(fresh.primary_route);
    expect(next.overlap).toBe(fresh.overlap);
  });
});

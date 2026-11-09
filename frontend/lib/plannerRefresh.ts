/**
 * Danger-distance slider refresh: merge a fresh server response into what is
 * already on screen.
 *
 * The map re-fits whenever the Route A, Route B or overlap objects change
 * identity, so for a route that is still there we keep those objects and take
 * everything else from the fresh response. Overlap does not depend on the
 * danger distance (ADR 0001); encounters, red spot hits, and, for a
 * recommendation, the score, explanation, tier and order all can.
 */
import type { CompareResponse, RecommendResponse, RouteResult, RouteView, ScoredRoute } from "@/lib/types";

export interface Ranking {
  routes: ScoredRoute[];
  selectedIndex: number;
}

/**
 * Same trip, different server response: identify a route by what it is, not
 * by its position in the list (ranking can change between requests).
 */
function routeKey(r: RouteResult): string {
  const g = r.geometry;
  const first = g[0];
  const last = g[g.length - 1];
  return [r.distance_km, r.duration_min, g.length, first?.lon, first?.lat, last?.lon, last?.lat].join("|");
}

/** A fresh recommendation, shown as is with the recommended route selected. */
export function rankingFrom(result: RecommendResponse): Ranking {
  return { routes: result.routes, selectedIndex: result.recommended_index };
}

/**
 * Re-rank the routes on screen by a fresh response. The list takes the fresh
 * order, scores, tiers and explanations; the selection stays on the route the
 * user was looking at, wherever it now ranks.
 *
 * When the candidate set itself changed, nothing on screen can be kept, so
 * this falls back to the fresh ranking with its recommended route selected.
 */
export function refreshRanking(current: Ranking, fresh: RecommendResponse): Ranking {
  const onScreen = new Map(current.routes.map((r) => [routeKey(r.route), r]));
  const sameSet =
    fresh.routes.length === current.routes.length && fresh.routes.every((r) => onScreen.has(routeKey(r.route)));
  if (!sameSet) return rankingFrom(fresh);

  const routes = fresh.routes.map((r) => {
    const kept = onScreen.get(routeKey(r.route))!;
    return { ...r, route: kept.route, overlap: kept.overlap };
  });
  const selected = current.routes[current.selectedIndex];
  const selectedIndex = selected
    ? routes.findIndex((r) => r.route === selected.route)
    : fresh.recommended_index;
  return { routes, selectedIndex: selectedIndex >= 0 ? selectedIndex : fresh.recommended_index };
}

/** A compare response as the Route A view the planner shows. */
export function comparisonFrom(result: CompareResponse): RouteView {
  return {
    route: result.primary_route,
    overlap: result.overlap,
    encounters: result.encounters,
    red_spot_hits: result.red_spots,
  };
}

/** Same as refreshRanking, for the comparison view's single Route A. */
export function refreshComparison(current: RouteView | null, fresh: CompareResponse): RouteView {
  const next = comparisonFrom(fresh);
  if (!current || routeKey(current.route) !== routeKey(next.route)) return next;
  return { ...next, route: current.route, overlap: current.overlap };
}

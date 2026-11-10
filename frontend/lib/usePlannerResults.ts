"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, compareRoutes, recommendRoutes } from "@/lib/api";
import {
  comparisonFrom,
  rankingFrom,
  refreshComparison,
  refreshRanking,
  type Ranking,
} from "@/lib/plannerRefresh";
import type { ComparisonView, LonLat, RedZoneBand, RouteResult, RouteView, TravelMode } from "@/lib/types";

/** "compare" is the primary view; "recommend" is the secondary, ranked one. */
export type PlannerView = "compare" | "recommend";

export interface PlannerInputs {
  primaryStart: LonLat | null;
  primaryEnd: LonLat | null;
  compareStart: LonLat | null;
  compareEnd: LonLat | null;
  mode: TravelMode;
  dangerDistance: number;
  avoidOverlap: boolean;
  avoidRedSpots: boolean;
}

/** What a slider refresh replays: the last request, with only the danger distance changed. */
type LastRequest = { view: PlannerView; inputs: PlannerInputs };

const IDLE_STATUS = "Enter both routes to compare";

export function usePlannerResults(inputs: PlannerInputs) {
  const [view, setView] = useState<PlannerView | null>(null);
  const [comparison, setComparison] = useState<ComparisonView | null>(null);
  const [ranking, setRanking] = useState<Ranking>({ routes: [], selectedIndex: 0 });
  const [comparisonRoute, setComparisonRoute] = useState<RouteResult | null>(null);
  const [redZoneBand, setRedZoneBand] = useState<RedZoneBand | null>(null);
  const [status, setStatus] = useState(IDLE_STATUS);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Which request is in flight, slider refreshes included.
  const [pending, setPending] = useState<PlannerView | null>(null);

  // Only the newest request may update the page (slider drags fire several).
  const seq = useRef(0);
  const last = useRef<LastRequest | null>(null);

  const canCompare = !!(inputs.primaryStart && inputs.primaryEnd && inputs.compareStart && inputs.compareEnd);
  const canRecommend = !!(inputs.primaryStart && inputs.primaryEnd);

  async function run(kind: PlannerView, req: PlannerInputs, refresh: boolean) {
    const { primaryStart, primaryEnd, compareStart, compareEnd } = req;
    if (!primaryStart || !primaryEnd) return;
    if (kind === "compare" && (!compareStart || !compareEnd)) return;

    const mySeq = ++seq.current;
    setPending(kind);
    setErrorMsg(null);
    if (!refresh) setStatus(kind === "compare" ? "Comparing routes…" : "Ranking alternatives…");

    try {
      if (kind === "compare") {
        const result = await compareRoutes({
          primaryStart,
          primaryEnd,
          comparisonStart: compareStart!,
          comparisonEnd: compareEnd!,
          mode: req.mode,
          dangerDistanceM: req.dangerDistance,
        });
        if (mySeq !== seq.current) return;
        setRedZoneBand(result.red_zone_band);
        if (refresh) {
          setComparison((cur) => refreshComparison(cur, result));
          return;
        }
        setComparison(comparisonFrom(result));
        setComparisonRoute(result.comparison_route);
        setView("compare");
        const n = result.overlap.segments.length;
        setStatus(n > 0 ? `${n} overlap area${n === 1 ? "" : "s"} detected` : "No meaningful overlap detected");
      } else {
        const result = await recommendRoutes({
          primaryStart,
          primaryEnd,
          comparisonStart: compareStart ?? undefined,
          comparisonEnd: compareEnd ?? undefined,
          mode: req.mode,
          dangerDistanceM: req.dangerDistance,
          avoidOverlap: req.avoidOverlap,
          avoidRedSpots: req.avoidRedSpots,
        });
        if (mySeq !== seq.current) return;
        setRedZoneBand(result.red_zone_band);
        if (refresh) {
          // Ranking depends on the danger distance, so re-rank, but keep the
          // route objects on screen so the map does not re-fit.
          setRanking((cur) => refreshRanking(cur, result));
          return;
        }
        setRanking(rankingFrom(result));
        setComparisonRoute(result.comparison_route);
        setView("recommend");
        const n = result.routes.length;
        setStatus(`${n} route${n === 1 ? "" : "s"} ranked`);
      }
    } catch (err) {
      if (mySeq !== seq.current) return;
      if (err instanceof ApiError) {
        setErrorMsg(err.message || "Couldn't find a route between these locations.");
      } else {
        setErrorMsg("Something went wrong. Check your connection and try again.");
      }
      if (!refresh && !last.current) setStatus(IDLE_STATUS);
    } finally {
      if (mySeq === seq.current) setPending(null);
    }
  }

  /** Forget the current result (e.g. the travel mode changed, so it no longer applies). */
  function reset() {
    seq.current++;
    last.current = null;
    setView(null);
    setComparison(null);
    setRanking({ routes: [], selectedIndex: 0 });
    setComparisonRoute(null);
    setRedZoneBand(null);
    setErrorMsg(null);
    setPending(null);
    setStatus(IDLE_STATUS);
  }

  function request(kind: PlannerView) {
    const req = { ...inputs };
    last.current = { view: kind, inputs: req };
    void run(kind, req, false);
  }

  // Moving the slider after a result redraws the band and re-asks (debounced)
  // for the last request at the new danger distance. Overlap does not depend
  // on it; encounters do, and so does a recommendation's ranking.
  useEffect(() => {
    const prev = last.current;
    if (!prev || !redZoneBand || prev.inputs.dangerDistance === inputs.dangerDistance) return;
    const t = setTimeout(() => {
      const req = { ...prev.inputs, dangerDistance: inputs.dangerDistance };
      last.current = { view: prev.view, inputs: req };
      void run(prev.view, req, true);
    }, 350);
    return () => clearTimeout(t);
    // Only a slider change should trigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputs.dangerDistance]);

  const selected: RouteView | undefined =
    view === "recommend" ? ranking.routes[ranking.selectedIndex] : view === "compare" ? comparison ?? undefined : undefined;

  return {
    view,
    selected,
    comparison,
    ranking,
    selectIndex: (i: number) => setRanking((cur) => ({ ...cur, selectedIndex: i })),
    // In the compare view Route B lives on the comparison itself, so a slider
    // refresh that changes it updates the map and the card together.
    comparisonRoute: view === "compare" && comparison ? comparison.comparison_route : comparisonRoute,
    redZoneBand,
    status,
    errorMsg,
    pending,
    loading: pending !== null,
    canCompare,
    canRecommend,
    reset,
    compare: () => request("compare"),
    recommend: () => request("recommend"),
  };
}

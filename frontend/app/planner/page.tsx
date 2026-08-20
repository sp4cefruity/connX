"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ConnXLogo from "@/components/ConnXLogo";
import LocationField from "@/components/LocationField";
import MapView from "@/components/MapView";
import RedSpotPanel from "@/components/RedSpotPanel";
import ResultsPanel from "@/components/ResultsPanel";
import { ApiError, createRedSpot, deleteRedSpot, listRedSpots, recommendRoutes } from "@/lib/api";
import type { GeocodeResult, LonLat, RedSpot, RouteResult, ScoredRoute, Sensitivity, TravelMode } from "@/lib/types";

type Endpoint = { label: string; point: LonLat | null };

export default function PlannerPage() {
  const [primaryStart, setPrimaryStart] = useState<Endpoint>({ label: "", point: null });
  const [primaryEnd, setPrimaryEnd] = useState<Endpoint>({ label: "", point: null });
  const [compareStart, setCompareStart] = useState<Endpoint>({ label: "", point: null });
  const [compareEnd, setCompareEnd] = useState<Endpoint>({ label: "", point: null });

  const [mode] = useState<TravelMode>("driving");
  const [sensitivity] = useState<Sensitivity>("medium");
  const [avoidOverlap, setAvoidOverlap] = useState(true);
  const [avoidRedSpots, setAvoidRedSpots] = useState(true);

  const [redSpots, setRedSpots] = useState<RedSpot[]>([]);
  const [pickingRedSpot, setPickingRedSpot] = useState(false);
  const [pendingPoint, setPendingPoint] = useState<LonLat | null>(null);

  const [routes, setRoutes] = useState<ScoredRoute[]>([]);
  const [comparisonRoute, setComparisonRoute] = useState<RouteResult | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [status, setStatus] = useState("Enter both routes to compare");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listRedSpots()
      .then(setRedSpots)
      .catch(() => {
        /* red spots are optional to load — app still functions (spec §36) */
      });
  }, []);

  function handleMapClick(lonLat: LonLat) {
    if (pickingRedSpot) {
      setPendingPoint(lonLat);
      setPickingRedSpot(false);
    }
  }

  async function handleAddRedSpot(payload: {
    name: string;
    radius_m: number;
    latitude: number;
    longitude: number;
  }) {
    try {
      const created = await createRedSpot(payload);
      setRedSpots((prev) => [...prev, created]);
    } finally {
      setPendingPoint(null);
    }
  }

  async function handleDeleteRedSpot(id: string) {
    setRedSpots((prev) => prev.filter((s) => s.id !== id));
    try {
      await deleteRedSpot(id);
    } catch {
      // reload from server on failure to stay in sync
      listRedSpots().then(setRedSpots).catch(() => {});
    }
  }

  const canCompare = primaryStart.point && primaryEnd.point;

  async function handleCompare() {
    if (!primaryStart.point || !primaryEnd.point) return;
    setLoading(true);
    setErrorMsg(null);
    setStatus("Finding routes…");

    try {
      setTimeout(() => setStatus("Comparing routes…"), 250);

      const result = await recommendRoutes({
        primaryStart: primaryStart.point,
        primaryEnd: primaryEnd.point,
        comparisonStart: compareStart.point ?? undefined,
        comparisonEnd: compareEnd.point ?? undefined,
        mode,
        sensitivity,
        avoidOverlap,
        avoidRedSpots,
      });

      setRoutes(result.routes);
      setSelectedIndex(result.recommended_index);
      setComparisonRoute(result.comparison_route);

      const overlapSegs = result.routes[result.recommended_index]?.overlap.segments.length ?? 0;
      setStatus(
        overlapSegs > 0
          ? `${overlapSegs} overlap area${overlapSegs === 1 ? "" : "s"} detected`
          : "No meaningful overlap detected"
      );
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message || "Couldn't find a route between these locations.");
      } else {
        setErrorMsg("Something went wrong. Check your connection and try again.");
      }
      setStatus("Enter both routes to compare");
    } finally {
      setLoading(false);
    }
  }

  const selected = routes[selectedIndex];

  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-[360px_1fr]">
      <aside className="flex flex-col overflow-y-auto border-r border-border bg-panel">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <ConnXLogo size={18} />
          <Link href="/" className="font-mono text-[11px] text-ink-dim hover:text-ink transition-colors">
            ← Home
          </Link>
        </div>

        <div className="border-b border-border px-5 py-5">
          <div className="mb-3.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
            <span className="h-1.5 w-1.5 rounded-full bg-route-a shadow-[0_0_6px_#5EE6C4]" />
            Your route
          </div>
          <LocationField
            label="Start"
            placeholder="Current location"
            value={primaryStart.label}
            onChange={(label) => setPrimaryStart((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => setPrimaryStart({ label: r.label, point: { lon: r.lon, lat: r.lat } })}
            showUseLocation
            onUseLocation={(loc) => setPrimaryStart({ label: "Current location", point: loc })}
          />
          <LocationField
            label="Destination"
            placeholder="Where to?"
            value={primaryEnd.label}
            onChange={(label) => setPrimaryEnd((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => setPrimaryEnd({ label: r.label, point: { lon: r.lon, lat: r.lat } })}
          />
        </div>

        <div className="border-b border-border px-5 py-5">
          <div className="mb-3.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
            <span className="h-1.5 w-1.5 rounded-full bg-route-b shadow-[0_0_6px_#B98CFF]" />
            Route to avoid
          </div>
          <LocationField
            label="Start"
            placeholder="Search location"
            value={compareStart.label}
            onChange={(label) => setCompareStart((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => setCompareStart({ label: r.label, point: { lon: r.lon, lat: r.lat } })}
          />
          <LocationField
            label="Destination"
            placeholder="Search location"
            value={compareEnd.label}
            onChange={(label) => setCompareEnd((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => setCompareEnd({ label: r.label, point: { lon: r.lon, lat: r.lat } })}
          />

          <div className="mt-3 flex flex-col gap-2 font-mono text-[11px] text-ink-dim">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={avoidOverlap} onChange={(e) => setAvoidOverlap(e.target.checked)} className="accent-route-a" />
              Avoid overlap
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={avoidRedSpots} onChange={(e) => setAvoidRedSpots(e.target.checked)} className="accent-ember" />
              Avoid red spots
            </label>
          </div>

          <button
            onClick={handleCompare}
            disabled={!canCompare || loading}
            className="mt-4 w-full rounded-md bg-route-b py-3 font-mono text-xs uppercase tracking-wider text-[#160A2E] transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Comparing…" : "Compare routes"}
          </button>

          {errorMsg && (
            <p className="mt-2.5 font-mono text-[11px] text-ember">{errorMsg}</p>
          )}
        </div>

        <div className="px-5 py-5">
          <RedSpotPanel
            redSpots={redSpots}
            onAdd={handleAddRedSpot}
            onDelete={handleDeleteRedSpot}
            pendingPoint={pendingPoint}
            onCancelPending={() => setPendingPoint(null)}
            onStartAdding={() => setPickingRedSpot(true)}
            isPicking={pickingRedSpot}
          />
        </div>
      </aside>

      <main className="relative bg-[#08080F]">
        <div className="pointer-events-none absolute inset-x-4 top-4 z-10 flex justify-between sm:inset-x-5">
          <span className="rounded-full border border-border bg-panel/70 px-2.5 py-1.5 font-mono text-[11px] text-ink-dim backdrop-blur-md">
            {pickingRedSpot ? "Tap the map to place your red spot" : status}
          </span>
          <span className="rounded-full border border-border bg-panel/70 px-2.5 py-1.5 font-mono text-[11px] capitalize text-ink-dim backdrop-blur-md">
            {mode}
          </span>
        </div>

        <MapView
          primaryRoute={selected?.route}
          comparisonRoute={comparisonRoute}
          overlapSegments={selected?.overlap.segments}
          redSpots={redSpots}
          onMapClick={handleMapClick}
        />

        <ResultsPanel
          routes={routes}
          selectedIndex={selectedIndex}
          onSelect={setSelectedIndex}
          overlapSummary={selected ? { distanceKm: selected.overlap.distance_km, percentage: selected.overlap.percentage } : null}
          redSpotCount={selected?.red_spot_hits.filter((h) => h.intersects).length}
        />
      </main>
    </div>
  );
}

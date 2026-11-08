"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import ConnXLogo from "@/components/ConnXLogo";
import LocationField from "@/components/LocationField";
import EncounterPanel from "@/components/EncounterPanel";
import RedSpotPanel from "@/components/RedSpotPanel";
import ResultsPanel from "@/components/ResultsPanel";
import { ApiError, recommendRoutes } from "@/lib/api";
import { encounterZoomPoints, withRefreshedEncounters, type ZoomTarget } from "@/lib/encounters";
import { useRedSpotEditor } from "@/lib/useRedSpotEditor";
import {
  DANGER_DISTANCE_DEFAULT_M,
  DANGER_DISTANCE_MAX_M,
  DANGER_DISTANCE_MIN_M,
} from "@/lib/types";
import type { GeocodeResult, LonLat, RedZoneBand, RouteResult, ScoredRoute, TravelMode } from "@/lib/types";

// maplibre-gl is a large dependency (200KB+ gzipped) that touches WebGL and
// `window` at module scope, which is incompatible with the server. A static
// import makes it part of the initial route bundle Next.js has to ship and
// hydrate before *anything* on this page is interactive — that's the actual
// cause of the multi-second load, not SSR of the component's output itself.
// `next/dynamic` with `ssr: false` moves it into its own chunk that's
// fetched only in the browser, after hydration, off the critical path. The
// sidebar (what people interact with first) becomes interactive immediately;
// the map streams in a beat later behind a lightweight skeleton.
const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-[#08080F]">
      <div className="flex items-center gap-2 font-mono text-[11px] text-ink-dim">
        <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        Loading map…
      </div>
    </div>
  ),
});

type Endpoint = { label: string; point: LonLat | null };

export default function PlannerPage() {
  const [primaryStart, setPrimaryStart] = useState<Endpoint>({ label: "", point: null });
  const [primaryEnd, setPrimaryEnd] = useState<Endpoint>({ label: "", point: null });
  const [compareStart, setCompareStart] = useState<Endpoint>({ label: "", point: null });
  const [compareEnd, setCompareEnd] = useState<Endpoint>({ label: "", point: null });

  // Search bias for LocationField. MapView doesn't report its centre yet, so this
  // starts at MapView's initial centre and follows the last picked location (the
  // map flies there). TODO: once MapView exposes `onMoveEnd?: (center: LonLat) => void`,
  // feed it into setMapCenter so the bias tracks manual panning too.
  const [mapCenter, setMapCenter] = useState<LonLat>({ lon: 85.8245, lat: 20.2961 });

  function selectResult(set: (e: Endpoint) => void, r: GeocodeResult) {
    const point = { lon: r.lon, lat: r.lat };
    set({ label: r.label, point });
    setMapCenter(point);
  }

  const [mode] = useState<TravelMode>("driving");
  // How close Route B may come before it counts as too close; sets the width
  // of the red zone band. Not the overlap tolerance (that is fixed server-side).
  const [dangerDistance, setDangerDistance] = useState(DANGER_DISTANCE_DEFAULT_M);
  const [avoidOverlap, setAvoidOverlap] = useState(true);
  const [avoidRedSpots, setAvoidRedSpots] = useState(true);

  const spots = useRedSpotEditor();

  const [routes, setRoutes] = useState<ScoredRoute[]>([]);
  const [comparisonRoute, setComparisonRoute] = useState<RouteResult | null>(null);
  const [redZoneBand, setRedZoneBand] = useState<RedZoneBand | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [zoomTarget, setZoomTarget] = useState<ZoomTarget | null>(null);
  const [status, setStatus] = useState("Enter both routes to compare");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canCompare = primaryStart.point && primaryEnd.point;

  // Moving the slider after a comparison redraws the band at the new width.
  // The band is built server-side, so re-ask (debounced) for the same trips;
  // overlap does not depend on the danger distance, so those numbers stay put.
  useEffect(() => {
    if (!redZoneBand) return;
    const t = setTimeout(() => handleCompare({ keepSelection: true }), 350);
    return () => clearTimeout(t);
    // Only a slider change should trigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dangerDistance]);

  // Only the newest request may update the page (slider drags fire several).
  const compareSeq = useRef(0);

  async function handleCompare(opts?: { keepSelection?: boolean }) {
    if (!primaryStart.point || !primaryEnd.point) return;
    const seq = ++compareSeq.current;
    const refresh = opts?.keepSelection ?? false; // slider refresh: keep status text as is
    setLoading(true);
    setErrorMsg(null);
    if (!refresh) setStatus("Finding routes…");

    try {
      if (!refresh) setTimeout(() => setStatus("Comparing routes…"), 250);

      const result = await recommendRoutes({
        primaryStart: primaryStart.point,
        primaryEnd: primaryEnd.point,
        comparisonStart: compareStart.point ?? undefined,
        comparisonEnd: compareEnd.point ?? undefined,
        mode,
        dangerDistanceM: dangerDistance,
        avoidOverlap,
        avoidRedSpots,
      });

      if (seq !== compareSeq.current) return;
      setRedZoneBand(result.red_zone_band);
      if (refresh) {
        // Slider refresh: only the band and the encounters changed. Leave the
        // routes, selection and map view alone (the map re-fits whenever route
        // objects change), and just carry the new encounters over.
        const carried = withRefreshedEncounters(routes, result.routes);
        if (carried) {
          setRoutes(carried);
        } else {
          // The candidate routes themselves changed: show the new set.
          setRoutes(result.routes);
          setSelectedIndex(result.recommended_index);
        }
        return;
      }
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
      if (seq !== compareSeq.current) return;
      if (err instanceof ApiError) {
        setErrorMsg(err.message || "Couldn't find a route between these locations.");
      } else {
        setErrorMsg("Something went wrong. Check your connection and try again.");
      }
      if (!refresh) setStatus("Enter both routes to compare");
    } finally {
      if (seq === compareSeq.current) setLoading(false);
    }
  }

  const selected = routes[selectedIndex];

  // Route A's red spot results. A spot only counts as hit while it is unchanged
  // since that comparison; edited spots are re-checked on the next compare.
  const hitSpotIds = useMemo(() => {
    const hits = selected?.red_spot_hits ?? [];
    return hits
      .filter((h) => {
        const current = spots.redSpots.find((s) => s.id === h.red_spot.id);
        return (
          h.intersects &&
          !!current &&
          current.latitude === h.red_spot.latitude &&
          current.longitude === h.red_spot.longitude &&
          current.radius_m === h.red_spot.radius_m
        );
      })
      .map((h) => h.red_spot.id);
  }, [selected, spots.redSpots]);

  // The saved copy of the spot being edited is replaced on the map by its draft.
  const mapRedSpots = useMemo(
    () => spots.redSpots.filter((s) => s.id !== spots.draft?.id),
    [spots.redSpots, spots.draft?.id]
  );

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
            bias={mapCenter}
            placeholder="Current location"
            value={primaryStart.label}
            onChange={(label) => setPrimaryStart((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => selectResult(setPrimaryStart, r)}
            showUseLocation
            onUseLocation={(loc) => {
              setPrimaryStart({ label: "Current location", point: loc });
              setMapCenter(loc);
            }}
          />
          <LocationField
            label="Destination"
            bias={mapCenter}
            placeholder="Where to?"
            value={primaryEnd.label}
            onChange={(label) => setPrimaryEnd((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => selectResult(setPrimaryEnd, r)}
          />
        </div>

        <div className="border-b border-border px-5 py-5">
          <div className="mb-3.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
            <span className="h-1.5 w-1.5 rounded-full bg-route-b shadow-[0_0_6px_#B98CFF]" />
            Route to avoid
          </div>
          <LocationField
            label="Start"
            bias={mapCenter}
            placeholder="Search location"
            value={compareStart.label}
            onChange={(label) => setCompareStart((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => selectResult(setCompareStart, r)}
          />
          <LocationField
            label="Destination"
            bias={mapCenter}
            placeholder="Search location"
            value={compareEnd.label}
            onChange={(label) => setCompareEnd((p) => ({ ...p, label }))}
            onSelect={(r: GeocodeResult) => selectResult(setCompareEnd, r)}
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

          <div className="mt-4 font-mono text-[11px] text-ink-dim">
            <label htmlFor="danger-distance" className="flex items-center justify-between">
              <span>Danger distance</span>
              <span className="text-ember">
                {dangerDistance >= 1000 ? `${dangerDistance / 1000} km` : `${dangerDistance} m`}
              </span>
            </label>
            <input
              id="danger-distance"
              type="range"
              min={DANGER_DISTANCE_MIN_M}
              max={DANGER_DISTANCE_MAX_M}
              step={50}
              value={dangerDistance}
              onChange={(e) => setDangerDistance(Number(e.target.value))}
              className="mt-2 w-full accent-ember"
            />
            <p className="mt-1 text-[10px] opacity-70">Shaded red on the map around their route.</p>
          </div>

          <button
            onClick={() => handleCompare()}
            disabled={!canCompare || loading}
            className="mt-4 w-full rounded-md bg-route-b py-3 font-mono text-xs uppercase tracking-wider text-[#160A2E] transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Comparing…" : "Compare routes"}
          </button>

          {errorMsg && (
            <p className="mt-2.5 font-mono text-[11px] text-ember">{errorMsg}</p>
          )}
        </div>

        {/* Only meaningful once a comparison against their route has run. */}
        {selected && comparisonRoute && (
          <div className="border-b border-border px-5 py-5">
            <EncounterPanel
              encounters={selected.encounters}
              routeDistanceKm={selected.route.distance_km}
              dangerDistanceM={dangerDistance}
              onSelect={(e) =>
                setZoomTarget({ points: encounterZoomPoints(e), key: (zoomTarget?.key ?? 0) + 1 })
              }
            />
          </div>
        )}

        <div className="px-5 py-5">
          <RedSpotPanel
            redSpots={spots.redSpots}
            hits={selected ? selected.red_spot_hits : null}
            checking={avoidRedSpots}
            draft={spots.draft}
            picking={spots.picking}
            saving={spots.saving}
            error={spots.error}
            onStartAdding={spots.startAdding}
            onEdit={spots.editAndFocus}
            onDelete={spots.remove}
            onChangeDraft={spots.patchDraft}
            onSave={spots.save}
            onCancel={spots.cancel}
          />
        </div>
      </aside>

      <main className="relative bg-[#08080F]">
        {/* Left-aligned and capped in width so it never runs under the zoom buttons (top-right). */}
        <div className="pointer-events-none absolute left-4 right-16 top-4 z-10 flex items-center gap-2 sm:left-5">
          <span className="truncate rounded-full border border-border bg-panel/70 px-2.5 py-1.5 font-mono text-[11px] text-ink-dim backdrop-blur-md">
            {spots.picking ? "Click the map to place your red spot" : spots.draft ? "Drag the dots to move or resize" : status}
          </span>
          <span className="shrink-0 rounded-full border border-border bg-panel/70 px-2.5 py-1.5 font-mono text-[11px] capitalize text-ink-dim backdrop-blur-md">
            {mode}
          </span>
        </div>

        <MapView
          primaryRoute={selected?.route}
          comparisonRoute={comparisonRoute}
          redZoneBand={redZoneBand}
          overlapSegments={selected?.overlap.segments}
          encounters={selected?.encounters}
          zoomTo={zoomTarget}
          redSpots={mapRedSpots}
          hitSpotIds={hitSpotIds}
          editor={spots.draft}
          onEditorChange={(patch) => spots.patchDraft(patch)}
          onSpotClick={spots.edit}
          focus={spots.focus}
          onMapClick={spots.handleMapClick}
          picking={spots.picking}
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

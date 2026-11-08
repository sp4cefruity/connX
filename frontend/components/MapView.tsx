"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { LonLat, OverlapSegment, RedSpot, RedZoneBand, RouteResult } from "@/lib/types";

// OpenFreeMap vector basemap (no API key). Configurable so the provider or
// style can be swapped without a code change (see ADR 0004).
const MAP_STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL || "https://tiles.openfreemap.org/styles/dark";

// App palette (mirrors frontend/tailwind.config.ts).
const PALETTE = {
  bg: "#0A0A12",
  panel: "#12131D",
  panel2: "#161826",
  ink: "#ECEEF5",
  inkDim: "#8A90A6",
  routeA: "#5EE6C4",
  routeB: "#B98CFF",
  ember: "#FF5A36",
};

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };
const SOURCE_IDS = ["primary-route", "comparison-route", "overlap-segments", "red-spots", "red-zone-band"];

/**
 * Where custom layers go: just below the basemap's label layers, but still
 * above roads, rails and buildings. Stock vector styles interleave a few
 * symbol layers early in the stack (e.g. water names, one-way arrows), so
 * "the first symbol layer" would bury the routes under the road fills.
 * Instead: the first text label that sits above every non-symbol basemap
 * layer. Returns undefined (add on top) if the style has no such label.
 */
function findLabelAnchor(map: maplibregl.Map): string | undefined {
  const layers = map.getStyle().layers ?? [];
  let lastBase = -1;
  layers.forEach((l, i) => {
    const { source, "source-layer": sourceLayer } = l as { source?: string; "source-layer"?: string };
    const isCustom = SOURCE_IDS.includes(source ?? "");
    // Boundaries are drawn above the road labels in OpenFreeMap; they are
    // irrelevant at route zoom, so they must not push the anchor past those.
    if (l.type !== "symbol" && l.type !== "background" && !isCustom && sourceLayer !== "boundary") {
      lastBase = i;
    }
  });
  for (let i = lastBase + 1; i < layers.length; i++) {
    const l = layers[i];
    if (l.type === "symbol" && l.layout && "text-field" in l.layout) return l.id;
  }
  return undefined;
}

/**
 * The single place that adds ConnX's own sources and layers (Route A, Route B,
 * overlap segments, red spots). Idempotent, so it can be called again on every
 * `style.load` — swapping the basemap style at runtime drops custom layers.
 */
function addCustomLayers(map: maplibregl.Map) {
  for (const id of SOURCE_IDS) {
    if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: EMPTY_FC });
  }

  const before = findLabelAnchor(map);
  const add = (layer: maplibregl.LayerSpecification) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer, before);
  };

  // Red zone band — translucent area of the danger distance around Route B,
  // below every route line.
  add({
    id: "red-zone-band-fill",
    type: "fill",
    source: "red-zone-band",
    paint: { "fill-color": PALETTE.ember, "fill-opacity": 0.16 },
  });
  // Comparison route (Route B) — underneath primary
  add({
    id: "comparison-route-line",
    type: "line",
    source: "comparison-route",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": PALETTE.routeB,
      "line-width": 5,
      "line-opacity": 0.8,
      "line-blur": 1,
    },
  });
  // Primary route (Route A) — on top with glow
  add({
    id: "primary-route-glow",
    type: "line",
    source: "primary-route",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": PALETTE.routeA,
      "line-width": 10,
      "line-opacity": 0.25,
      "line-blur": 6,
    },
  });
  add({
    id: "primary-route-line",
    type: "line",
    source: "primary-route",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": PALETTE.routeA,
      "line-width": 4,
      "line-opacity": 0.95,
    },
  });
  // Overlap segments — thick red on top of the routes
  add({
    id: "overlap-line",
    type: "line",
    source: "overlap-segments",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": PALETTE.ember,
      "line-width": 7,
      "line-opacity": 0.92,
      "line-blur": 1,
    },
  });
  add({
    id: "red-spot-fill",
    type: "fill",
    source: "red-spots",
    paint: { "fill-color": PALETTE.ember, "fill-opacity": 0.1 },
  });
  add({
    id: "red-spot-outline",
    type: "line",
    source: "red-spots",
    paint: {
      "line-color": PALETTE.ember,
      "line-width": 1.5,
      "line-dasharray": [3, 2],
      "line-opacity": 0.55,
    },
  });
}

/**
 * Retint the stock OpenFreeMap dark style to the app palette by overriding
 * paint properties after the style loads (no forked style file). Layer ids not
 * present in the loaded style are skipped, so a different configured style
 * degrades to "stock" instead of throwing.
 */
function tuneDarkStyle(map: maplibregl.Map) {
  const paint = (id: string, prop: string, value: unknown) => {
    if (map.getLayer(id)) map.setPaintProperty(id, prop, value);
  };

  paint("background", "background-color", PALETTE.bg);
  paint("water", "fill-color", "#0E1626");
  paint("waterway", "line-color", "#0E1626");
  paint("landcover_ice_shelf", "fill-color", PALETTE.panel);
  paint("landcover_glacier", "fill-color", PALETTE.panel);
  paint("landuse_residential", "fill-color", "#0E0F19");
  paint("landuse_residential", "fill-opacity", 0.6);
  paint("landuse_park", "fill-color", "#0F1A1B");
  paint("landcover_wood", "fill-color", "#0F1A1B");
  // The wood layer uses a sprite pattern that ignores fill-color; hide it and
  // let landuse_park carry the greenery.
  if (map.getLayer("landcover_wood")) map.setLayoutProperty("landcover_wood", "visibility", "none");
  paint("building", "fill-color", "#11121D");
  paint("building", "fill-outline-color", "#1A1C2C");

  // Roads: lighter than the land so streets read, quiet enough for routes.
  paint("highway_path", "line-color", "#23263A");
  paint("highway_minor", "line-color", "#1D2033");
  paint("highway_major_casing", "line-color", "#0A0A12");
  paint("highway_major_inner", "line-color", "#272A42");
  paint("highway_major_subtle", "line-color", "#272A42");
  paint("highway_motorway_casing", "line-color", "#0A0A12");
  paint("highway_motorway_inner", "line-color", "#33375A");
  paint("highway_motorway_subtle", "line-color", "#272A42");
  paint("aeroway-taxiway", "line-color", "#1D2033");
  paint("aeroway-runway", "line-color", "#272A42");
  paint("aeroway-area", "fill-color", PALETTE.panel2);
  for (const id of ["railway", "railway_minor", "railway_transit"]) paint(id, "line-color", "#1E2134");
  for (const id of ["railway_dashline", "railway_minor_dashline", "railway_transit_dashline"]) {
    paint(id, "line-color", PALETTE.bg);
  }
  paint("boundary_state", "line-color", "#2A2D44");
  paint("boundary_country_z0-4", "line-color", "#33375A");
  paint("boundary_country_z5-", "line-color", "#33375A");

  // Labels: ink-dim on a bg-coloured halo so they stay crisp over any fill.
  const labelIds = [
    "water_name",
    "highway_name_other",
    "highway_name_motorway",
    "place_other",
    "place_suburb",
    "place_village",
    "place_town",
    "place_city",
    "place_city_large",
    "place_state",
    "place_country_other",
    "place_country_minor",
    "place_country_major",
  ];
  for (const id of labelIds) {
    paint(id, "text-color", id === "water_name" ? "#4C5A7A" : PALETTE.inkDim);
    paint(id, "text-halo-color", PALETTE.bg);
    paint(id, "text-halo-width", 1.5);
    paint(id, "text-halo-blur", 0.5);
  }
  for (const id of ["place_city", "place_city_large", "place_country_major"]) {
    paint(id, "text-color", PALETTE.ink);
  }
}

function toLineString(points: LonLat[]) {
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: points.map((p) => [p.lon, p.lat]),
    },
  };
}

function toCircle(spot: RedSpot, steps = 48) {
  const coords: [number, number][] = [];
  const metersPerDegLat = 111_320;
  const cosLat = Math.cos((spot.latitude * Math.PI) / 180);
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dx = (spot.radius_m * Math.cos(angle)) / (metersPerDegLat * cosLat);
    const dy = (spot.radius_m * Math.sin(angle)) / metersPerDegLat;
    coords.push([spot.longitude + dx, spot.latitude + dy]);
  }
  return {
    type: "Feature" as const,
    properties: { name: spot.name },
    geometry: { type: "Polygon" as const, coordinates: [coords] },
  };
}

interface MapViewProps {
  primaryRoute?: RouteResult | null;
  comparisonRoute?: RouteResult | null;
  overlapSegments?: OverlapSegment[];
  /** Route B buffered by the danger distance (from the API). */
  redZoneBand?: RedZoneBand | null;
  redSpots?: RedSpot[];
  onMapClick?: (lonLat: LonLat) => void;
  /** True while the user is placing a red spot — shows a crosshair cursor. */
  picking?: boolean;
}

export default function MapView({
  primaryRoute,
  comparisonRoute,
  overlapSegments = [],
  redZoneBand = null,
  redSpots = [],
  onMapClick,
  picking = false,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);
  // The map is created once, but `onMapClick` is a fresh closure every
  // render (it closes over planner state like `pickingRedSpot`). Going
  // through a ref means the registered handler always calls the latest one
  // instead of the first-render copy where every flag was still false.
  const clickHandlerRef = useRef(onMapClick);
  // Same idea for the data: `style.load` handlers (registered once) must push
  // the latest data when layers are re-added, not the first render's.
  const dataRef = useRef({ primaryRoute, comparisonRoute, overlapSegments, redZoneBand, redSpots });
  useEffect(() => {
    clickHandlerRef.current = onMapClick;
    dataRef.current = { primaryRoute, comparisonRoute, overlapSegments, redZoneBand, redSpots };
  });

  // While placing a red spot the map should feel like a target, not a pan
  // surface: crosshair cursor and no double-tap zoom stealing quick taps.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !picking) return;
    const canvas = map.getCanvas();
    canvas.style.cursor = "crosshair";
    map.doubleClickZoom.disable();
    return () => {
      canvas.style.cursor = "";
      map.doubleClickZoom.enable();
    };
  }, [picking]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: [85.8245, 20.2961],
      zoom: 12,
      maxZoom: 19,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    // Fires for the initial style and again after every setStyle(), so custom
    // layers always survive a style swap.
    map.on("style.load", () => {
      loadedRef.current = true;
      tuneDarkStyle(map);
      addCustomLayers(map);
      pushData(map, false);
    });

    map.on("click", (e) => clickHandlerRef.current?.({ lon: e.lngLat.lng, lat: e.lngLat.lat }));

    return () => {
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Writes the latest data into the custom sources; optionally fits the view
  // to the routes (only when the data changed, not on a style reload).
  function pushData(map: maplibregl.Map, fit: boolean) {
    const { primaryRoute, comparisonRoute, overlapSegments, redZoneBand, redSpots } = dataRef.current;

    const primarySrc = map.getSource("primary-route") as maplibregl.GeoJSONSource | undefined;
    const comparisonSrc = map.getSource("comparison-route") as maplibregl.GeoJSONSource | undefined;
    const overlapSrc = map.getSource("overlap-segments") as maplibregl.GeoJSONSource | undefined;
    const redSpotSrc = map.getSource("red-spots") as maplibregl.GeoJSONSource | undefined;

    primarySrc?.setData({
      type: "FeatureCollection",
      features: primaryRoute ? [toLineString(primaryRoute.geometry)] : [],
    });
    comparisonSrc?.setData({
      type: "FeatureCollection",
      features: comparisonRoute ? [toLineString(comparisonRoute.geometry)] : [],
    });
    overlapSrc?.setData({
      type: "FeatureCollection",
      features: overlapSegments.map((s) => toLineString(s.geometry)),
    });
    redSpotSrc?.setData({
      type: "FeatureCollection",
      features: redSpots.map((s) => toCircle(s)),
    });
    (map.getSource("red-zone-band") as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: redZoneBand ? [{ type: "Feature", properties: {}, geometry: redZoneBand }] : [],
    });

    if (!fit) return;
    // Fit bounds to show both routes
    const allPoints = [
      ...(primaryRoute?.geometry ?? []),
      ...(comparisonRoute?.geometry ?? []),
    ];
    if (allPoints.length > 1) {
      const lons = allPoints.map((p) => p.lon);
      const lats = allPoints.map((p) => p.lat);
      map.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        { padding: 80, duration: 800, maxZoom: 15 }
      );
    }
  }

  // The band changes on its own when the danger distance moves; don't re-fit
  // the view for that.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    pushData(map, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redZoneBand]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    pushData(map, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primaryRoute, comparisonRoute, overlapSegments, redSpots]);

  return <div ref={containerRef} className="h-full w-full" />;
}

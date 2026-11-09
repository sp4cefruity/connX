"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import {
  EDITOR_SOURCE_IDS,
  attachRedSpotInteractions,
  editorFeatureCollections,
  type EditorGeometry,
  type EditorPatch,
} from "@/lib/redSpotMap";
import { basemapOverrides } from "@/lib/basemapStyle";
import { DEFAULT_THEME, THEMES, type Theme, type ThemeName } from "@/lib/palette";
import { basemapStyleUrl, customLayerIds } from "@/lib/mapTheme";
import { circleRing } from "@/lib/redSpots";
import { formatGap, type ZoomTarget } from "@/lib/encounters";
import { fitPadding, isDesktopLayout, type Padding } from "@/lib/layout";
import type { Encounter, LonLat, OverlapSegment, RedSpot, RedZoneBand, RouteResult } from "@/lib/types";

// OpenFreeMap vector basemap (no API key). Configurable so the provider or
// style can be swapped without a code change (see ADR 0004).
// The light style defaults to the same structure retinted (NEXT_PUBLIC_MAP_STYLE_URL_LIGHT overrides).
const STYLE_URLS = basemapStyleUrl(process.env.NEXT_PUBLIC_MAP_STYLE_URL, process.env.NEXT_PUBLIC_MAP_STYLE_URL_LIGHT);

// Colours come from lib/palette.ts (also the source of the CSS variables).

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };
// A stable default, so an omitted prop doesn't look like new data on every render.
const EMPTY_ENCOUNTERS: Encounter[] = [];
const SOURCE_IDS = [
  "primary-route",
  "comparison-route",
  "overlap-segments",
  "red-spots",
  "red-zone-band",
  "encounter-markers",
  ...EDITOR_SOURCE_IDS,
];

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
function addCustomLayers(map: maplibregl.Map, theme: Theme) {
  const ROLE = theme.roles;
  const UI = theme.ui;
  const OPACITY = theme.mapOpacity;
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
    paint: { "fill-color": ROLE.redZone.color, "fill-opacity": OPACITY.band },
  });
  // Comparison route (Route B) — underneath primary
  add({
    id: "comparison-route-line",
    type: "line",
    source: "comparison-route",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ROLE.routeB.color,
      "line-width": 5,
      "line-opacity": ROLE.routeB.opacity,
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
      "line-color": ROLE.routeA.color,
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
      "line-color": ROLE.routeA.color,
      "line-width": 4,
      "line-opacity": ROLE.routeA.opacity,
    },
  });
  // Overlap segments — thick red on top of the routes
  add({
    id: "overlap-line",
    type: "line",
    source: "overlap-segments",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ROLE.overlap.color,
      "line-width": 7,
      "line-opacity": ROLE.overlap.opacity,
      "line-blur": 1,
    },
  });
  // Encounter markers: one dot at the closest point of each close pass, labelled
  // with the gap. Above the routes so a marker is never buried by its own line.
  add({
    id: "encounter-marker",
    type: "circle",
    source: "encounter-markers",
    paint: {
      "circle-radius": 7,
      "circle-color": ROLE.encounter.color,
      "circle-stroke-color": UI.bg,
      "circle-stroke-width": 2.5,
    },
  });
  add({
    id: "encounter-label",
    type: "symbol",
    source: "encounter-markers",
    layout: {
      "text-field": ["get", "label"],
      // Served by the default OpenFreeMap glyphs; a custom NEXT_PUBLIC_MAP_STYLE_URL must offer it too.
      "text-font": ["Noto Sans Bold"],
      "text-size": 12,
      "text-offset": [0, -1.4],
      "text-anchor": "bottom",
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": ROLE.encounter.color,
      "text-halo-color": UI.bg,
      "text-halo-width": 2,
    },
  });
  add({
    id: "red-spot-fill",
    type: "fill",
    source: "red-spots",
    // Spots that Route A hits are filled more strongly.
    paint: { "fill-color": ROLE.redZone.color, "fill-opacity": ["case", ["boolean", ["get", "hit"], false], OPACITY.spotHitFill, OPACITY.spotFill] },
  });
  add({
    id: "red-spot-outline",
    type: "line",
    source: "red-spots",
    paint: {
      "line-color": ROLE.redZone.color,
      "line-width": 1.5,
      "line-dasharray": [3, 2],
      "line-opacity": OPACITY.spotOutline,
    },
  });
  // Red spot hit: solid, heavier outline on top of the dashed one.
  add({
    id: "red-spot-hit-outline",
    type: "line",
    source: "red-spots",
    filter: ["==", ["get", "hit"], true],
    paint: { "line-color": ROLE.redZone.color, "line-width": 3, "line-opacity": ROLE.redZone.opacity },
  });
  // The spot being drawn / edited, and its drag handles (centre = move, edge = resize).
  add({
    id: "red-spot-draft-fill",
    type: "fill",
    source: "red-spot-draft",
    paint: { "fill-color": ROLE.redZone.color, "fill-opacity": OPACITY.draftFill },
  });
  add({
    id: "red-spot-draft-outline",
    type: "line",
    source: "red-spot-draft",
    paint: { "line-color": ROLE.redZone.color, "line-width": 2.5, "line-opacity": ROLE.redZone.opacity },
  });
  add({
    id: "red-spot-handles",
    type: "circle",
    source: "red-spot-handles",
    paint: {
      "circle-radius": 9,
      "circle-color": ["match", ["get", "kind"], "radius", UI.ink, ROLE.redZone.color],
      "circle-stroke-color": ["match", ["get", "kind"], "radius", ROLE.redZone.color, UI.ink],
      "circle-stroke-width": 3,
    },
  });
}

/**
 * Retint the stock OpenFreeMap style to the theme (see lib/basemapStyle.ts)
 * by overriding paint properties after the style loads. Layer ids not present
 * in the loaded style are skipped, so a different configured style degrades
 * to "stock" instead of throwing.
 */
function tuneBasemap(map: maplibregl.Map, theme: Theme) {
  for (const { layer, prop, value } of basemapOverrides(theme)) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, prop, value);
  }
  // The wood layer uses a sprite pattern that ignores fill-color; hide it and
  // let landuse_park carry the greenery.
  if (map.getLayer("landcover_wood")) map.setLayoutProperty("landcover_wood", "visibility", "none");
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

function toCircle(spot: RedSpot, hit: boolean) {
  return {
    type: "Feature" as const,
    properties: { id: spot.id, name: spot.name, hit },
    geometry: {
      type: "Polygon" as const,
      coordinates: [circleRing({ lon: spot.longitude, lat: spot.latitude }, spot.radius_m, 48)],
    },
  };
}

function toEncounterMarkers(encounters: Encounter[]) {
  return {
    type: "FeatureCollection" as const,
    features: encounters.map((e, i) => ({
      type: "Feature" as const,
      properties: { index: i, label: formatGap(e.min_gap_m) },
      geometry: { type: "Point" as const, coordinates: [e.location.lon, e.location.lat] },
    })),
  };
}

interface MapViewProps {
  primaryRoute?: RouteResult | null;
  comparisonRoute?: RouteResult | null;
  overlapSegments?: OverlapSegment[];
  /** Close passes of the selected route; drawn as markers labelled with the gap. */
  encounters?: Encounter[];
  /** Fit the view to these points whenever its `key` changes (e.g. a clicked encounter). */
  zoomTo?: ZoomTarget | null;
  /** Route B buffered by the danger distance (from the API). */
  redZoneBand?: RedZoneBand | null;
  redSpots?: RedSpot[];
  /** Ids of saved red spots that Route A hits (drawn highlighted). */
  hitSpotIds?: string[];
  /** Geometry of the red spot being drawn / edited; shows its circle and drag handles. */
  editor?: EditorGeometry | null;
  /** Called while a handle is dragged. The caller owns the value and clamps the radius. */
  onEditorChange?: (patch: EditorPatch) => void;
  /** A saved red spot was clicked on the map. */
  onSpotClick?: (id: string) => void;
  /** Pan to this point whenever `key` changes. */
  focus?: { lon: number; lat: number; key: number } | null;
  onMapClick?: (lonLat: LonLat) => void;
  /** True while the user is placing a red spot — shows a crosshair cursor. */
  picking?: boolean;
  /** Basemap and layer colours; switching it at runtime restyles the live map. */
  theme?: ThemeName;
}

// Fit padding that still fits the map's current size (a phone's map is short).
function paddingFor(map: maplibregl.Map, desired: Padding) {
  const el = map.getContainer();
  return fitPadding(el.clientWidth, el.clientHeight, desired);
}

export default function MapView({
  primaryRoute,
  comparisonRoute,
  overlapSegments = [],
  encounters = EMPTY_ENCOUNTERS,
  zoomTo = null,
  redZoneBand = null,
  redSpots = [],
  hitSpotIds,
  editor = null,
  onEditorChange,
  onSpotClick,
  focus = null,
  onMapClick,
  picking = false,
  theme = DEFAULT_THEME,
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
  const dataRef = useRef({ primaryRoute, comparisonRoute, overlapSegments, redZoneBand, encounters });
  // Red spot drawing state, read by handlers that are registered once.
  const spotStateRef = useRef({ redSpots, hitSpotIds, editor, picking, onEditorChange, onSpotClick });
  const interactionsRef = useRef(false);
  // The theme the basemap and custom layers are currently drawn in.
  const themeRef = useRef(theme);
  const appliedThemeRef = useRef<ThemeName | null>(null);
  useEffect(() => {
    themeRef.current = theme;
    clickHandlerRef.current = onMapClick;
    dataRef.current = { primaryRoute, comparisonRoute, overlapSegments, redZoneBand, encounters };
    spotStateRef.current = { redSpots, hitSpotIds, editor, picking, onEditorChange, onSpotClick };
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
      style: STYLE_URLS[themeRef.current],
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
      appliedThemeRef.current = themeRef.current;
      tuneBasemap(map, THEMES[themeRef.current]);
      addCustomLayers(map, THEMES[themeRef.current]);
      pushData(map, false);
      pushSpotData(map);
      if (!interactionsRef.current) {
        interactionsRef.current = true;
        attachRedSpotInteractions(map, {
          getEditor: () => spotStateRef.current.editor,
          onEditorChange: (patch) => spotStateRef.current.onEditorChange?.(patch),
          isPicking: () => spotStateRef.current.picking,
          onSpotClick: (id) => spotStateRef.current.onSpotClick?.(id),
        });
      }
    });

    map.on("click", (e) => clickHandlerRef.current?.({ lon: e.lngLat.lng, lat: e.lngLat.lat }));

    return () => {
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Theme switch at runtime. A different style URL goes through setStyle (the
  // style.load handler above re-adds the custom layers); the same URL is just
  // retinted in place, which avoids reloading the basemap. Either way the
  // custom sources keep their data.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || appliedThemeRef.current === theme) return;
    if (STYLE_URLS[appliedThemeRef.current ?? DEFAULT_THEME] !== STYLE_URLS[theme]) {
      map.setStyle(STYLE_URLS[theme], { diff: false });
      return;
    }
    appliedThemeRef.current = theme;
    for (const id of customLayerIds(map, SOURCE_IDS)) map.removeLayer(id);
    tuneBasemap(map, THEMES[theme]);
    addCustomLayers(map, THEMES[theme]);
  }, [theme]);

  // Writes the latest data into the custom sources; optionally fits the view
  // to the routes (only when the data changed, not on a style reload).
  function pushData(map: maplibregl.Map, fit: boolean) {
    const { primaryRoute, comparisonRoute, overlapSegments, redZoneBand, encounters } = dataRef.current;

    const primarySrc = map.getSource("primary-route") as maplibregl.GeoJSONSource | undefined;
    const comparisonSrc = map.getSource("comparison-route") as maplibregl.GeoJSONSource | undefined;
    const overlapSrc = map.getSource("overlap-segments") as maplibregl.GeoJSONSource | undefined;

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
    (map.getSource("encounter-markers") as maplibregl.GeoJSONSource | undefined)?.setData(
      toEncounterMarkers(encounters)
    );
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
        { padding: paddingFor(map, { top: 80, right: 80, bottom: isDesktopLayout() ? 300 : 80, left: 80 }), duration: 800, maxZoom: 15 }
      );
    }
  }

  // The band and the encounters change on their own when the danger distance
  // moves (or another route is selected); don't re-fit the view for that.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    pushData(map, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redZoneBand, encounters]);

  // Red spots and the drawing editor update separately from the routes so that
  // editing a spot never re-fits the view to the routes.
  function pushSpotData(map: maplibregl.Map) {
    const { redSpots, hitSpotIds, editor } = spotStateRef.current;
    const hits = new Set(hitSpotIds ?? []);
    const saved = map.getSource("red-spots") as maplibregl.GeoJSONSource | undefined;
    const draft = map.getSource("red-spot-draft") as maplibregl.GeoJSONSource | undefined;
    const handles = map.getSource("red-spot-handles") as maplibregl.GeoJSONSource | undefined;

    saved?.setData({
      type: "FeatureCollection",
      features: redSpots.map((s) => toCircle(s, hits.has(s.id))),
    });
    const editorData = editorFeatureCollections(editor);
    draft?.setData(editorData.draft);
    handles?.setData(editorData.handles);
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    pushData(map, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primaryRoute, comparisonRoute, overlapSegments]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    pushSpotData(map);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redSpots, hitSpotIds, editor]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    map.easeTo({ center: [focus.lon, focus.lat], zoom: Math.max(map.getZoom(), 14), duration: 600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.key]);

  // Zoom to a clicked encounter. On desktop the bottom padding clears the
  // results panel that overlays the lower part of the map; on phones the
  // results are in the bottom sheet instead.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !zoomTo || zoomTo.points.length === 0) return;
    const lons = zoomTo.points.map((p) => p.lon);
    const lats = zoomTo.points.map((p) => p.lat);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      {
        padding: paddingFor(map, { top: 90, left: 90, right: 90, bottom: isDesktopLayout() ? 260 : 90 }),
        maxZoom: 17,
        duration: 700,
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomTo?.key]);

  return <div ref={containerRef} className="h-full w-full" />;
}

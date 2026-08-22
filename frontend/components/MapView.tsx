"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { LonLat, OverlapSegment, RedSpot, RouteResult } from "@/lib/types";

// Raster dark basemap — pre-rendered tile images, far faster than vector tiles.
// Three subdomains for parallel download; retina @2x for sharp labels.
const RASTER_STYLE = {
  version: 8,
  sources: {
    "carto-dark": {
      type: "raster" as const,
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [
    {
      id: "carto-dark-layer",
      type: "raster" as const,
      source: "carto-dark",
      maxzoom: 19,
      // Lift the raw tile's blacks and flatten its contrast so the theme
      // reads as a soft, legible dark mode instead of pitch black. This is
      // applied directly on the GPU-composited raster layer (no extra tile
      // requests, no new provider/API key), so it's effectively free.
      paint: {
        "raster-brightness-min": 0.14,
        "raster-brightness-max": 0.92,
        "raster-contrast": -0.15,
        "raster-saturation": -0.1,
      },
    },
  ],
};

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
  redSpots?: RedSpot[];
  onMapClick?: (lonLat: LonLat) => void;
  /** True while the user is placing a red spot — shows a crosshair cursor. */
  picking?: boolean;
}

export default function MapView({
  primaryRoute,
  comparisonRoute,
  overlapSegments = [],
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
  useEffect(() => {
    clickHandlerRef.current = onMapClick;
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
      style: RASTER_STYLE as any,
      center: [85.8245, 20.2961],
      zoom: 12,
      maxZoom: 19,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      loadedRef.current = true;

      map.addSource("primary-route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addSource("comparison-route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addSource("overlap-segments", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addSource("red-spots", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      // Comparison route — underneath primary
      map.addLayer({
        id: "comparison-route-line",
        type: "line",
        source: "comparison-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#B98CFF",
          "line-width": 5,
          "line-opacity": 0.8,
          "line-blur": 1,
        },
      });
      // Primary route — on top with glow
      map.addLayer({
        id: "primary-route-glow",
        type: "line",
        source: "primary-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#5EE6C4",
          "line-width": 10,
          "line-opacity": 0.25,
          "line-blur": 6,
        },
      });
      map.addLayer({
        id: "primary-route-line",
        type: "line",
        source: "primary-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#5EE6C4",
          "line-width": 4,
          "line-opacity": 0.95,
        },
      });
      // Overlap segments — thick red on top of everything
      map.addLayer({
        id: "overlap-line",
        type: "line",
        source: "overlap-segments",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#FF5A36",
          "line-width": 7,
          "line-opacity": 0.92,
          "line-blur": 1,
        },
      });
      map.addLayer({
        id: "red-spot-fill",
        type: "fill",
        source: "red-spots",
        paint: { "fill-color": "#FF5A36", "fill-opacity": 0.1 },
      });
      map.addLayer({
        id: "red-spot-outline",
        type: "line",
        source: "red-spots",
        paint: {
          "line-color": "#FF5A36",
          "line-width": 1.5,
          "line-dasharray": [3, 2],
          "line-opacity": 0.55,
        },
      });

      applyData();
    });

    map.on("click", (e) => clickHandlerRef.current?.({ lon: e.lngLat.lng, lat: e.lngLat.lat }));

    return () => {
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyData() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;

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

  useEffect(() => {
    applyData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primaryRoute, comparisonRoute, overlapSegments, redSpots]);

  return <div ref={containerRef} className="h-full w-full" />;
}

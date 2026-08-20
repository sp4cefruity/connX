"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { LonLat, OverlapSegment, RedSpot, RouteResult } from "@/lib/types";

// Free, no-key vector basemap. Swap for a self-hosted style / Mapbox style
// URL in production — see README.
const MAP_STYLE = "https://demotiles.maplibre.org/style.json";

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
  // Rough metre-radius circle around a lon/lat point (equirectangular,
  // matches the backend's approximation — fine at this zoom level).
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
}

export default function MapView({
  primaryRoute,
  comparisonRoute,
  overlapSegments = [],
  redSpots = [],
  onMapClick,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [85.8245, 20.2961],
      zoom: 12,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      loadedRef.current = true;

      map.addSource("primary-route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("comparison-route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("overlap-segments", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("red-spots", { type: "geojson", data: { type: "FeatureCollection", features: [] } });

      map.addLayer({
        id: "comparison-route-line",
        type: "line",
        source: "comparison-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#B98CFF", "line-width": 4, "line-opacity": 0.85 },
      });
      map.addLayer({
        id: "primary-route-line",
        type: "line",
        source: "primary-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#5EE6C4", "line-width": 4, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "overlap-line",
        type: "line",
        source: "overlap-segments",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FF5A36", "line-width": 6, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "red-spot-fill",
        type: "fill",
        source: "red-spots",
        paint: { "fill-color": "#FF5A36", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "red-spot-outline",
        type: "line",
        source: "red-spots",
        paint: { "line-color": "#FF5A36", "line-width": 1.5, "line-dasharray": [2, 2], "line-opacity": 0.6 },
      });

      // apply any data that arrived before load finished
      applyData();
    });

    if (onMapClick) {
      map.on("click", (e) => onMapClick({ lon: e.lngLat.lng, lat: e.lngLat.lat }));
    }

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

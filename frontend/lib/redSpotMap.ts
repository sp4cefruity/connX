import type maplibregl from "maplibre-gl";
import type { MapLayerMouseEvent, MapLayerTouchEvent } from "maplibre-gl";
import { circleRing, metersBetween, offsetEast } from "./redSpots";
import type { LonLat } from "./types";

/** Geometry of the red spot currently being drawn or edited. */
export interface EditorGeometry {
  lon: number;
  lat: number;
  radius_m: number;
}

export type EditorPatch = Partial<EditorGeometry>;

// Layer / source ids. The layers themselves are added in MapView's
// `addCustomLayers` (the single layer helper) so they sit below the labels.
export const SAVED_SPOT_FILL_LAYER = "red-spot-fill";
export const EDITOR_HANDLE_LAYER = "red-spot-handles";
export const EDITOR_SOURCE_IDS = ["red-spot-draft", "red-spot-handles"];

/** Polygon + handle points for the spot being edited (empty when not editing). */
export function editorFeatureCollections(editor: EditorGeometry | null) {
  if (!editor) {
    return {
      draft: { type: "FeatureCollection" as const, features: [] },
      handles: { type: "FeatureCollection" as const, features: [] },
    };
  }
  const center: LonLat = { lon: editor.lon, lat: editor.lat };
  const edge = offsetEast(center, editor.radius_m);
  return {
    draft: {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: {},
          geometry: { type: "Polygon" as const, coordinates: [circleRing(center, editor.radius_m)] },
        },
      ],
    },
    handles: {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: { kind: "radius" },
          geometry: { type: "Point" as const, coordinates: [edge.lon, edge.lat] },
        },
        {
          type: "Feature" as const,
          properties: { kind: "center" },
          geometry: { type: "Point" as const, coordinates: [center.lon, center.lat] },
        },
      ],
    },
  };
}

export interface RedSpotMapCallbacks {
  /** Latest geometry of the spot being edited, or null. Read on every drag event. */
  getEditor: () => EditorGeometry | null;
  onEditorChange: (patch: EditorPatch) => void;
  /** True while the user is placing a new spot (clicks then place, not select). */
  isPicking: () => boolean;
  onSpotClick: (id: string) => void;
}

/**
 * Wires up red spot interaction on the map: dragging the centre / radius
 * handles of the spot being edited, and click-to-select on saved spots.
 *
 * Layer-bound listeners reference layers by id, so one registration survives
 * style swaps that remove and re-add the layers. Call once, after the layers
 * exist (MapView does it on the first `style.load`).
 */
export function attachRedSpotInteractions(map: maplibregl.Map, cb: RedSpotMapCallbacks) {
  const canvas = map.getCanvas();
  let dragging: "center" | "radius" | null = null;

  const onMove = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
    const editor = cb.getEditor();
    if (!dragging || !editor) return;
    const pointer: LonLat = { lon: e.lngLat.lng, lat: e.lngLat.lat };
    if (dragging === "center") {
      cb.onEditorChange({ lon: pointer.lon, lat: pointer.lat });
    } else {
      // Caller clamps to the 50 m - 2 km limits.
      cb.onEditorChange({ radius_m: metersBetween({ lon: editor.lon, lat: editor.lat }, pointer) });
    }
  };

  const stop = () => {
    dragging = null;
    map.off("mousemove", onMove);
    map.off("touchmove", onMove);
    map.dragPan.enable();
    canvas.style.cursor = "";
  };

  const start = (e: MapLayerMouseEvent | MapLayerTouchEvent) => {
    const kind = e.features?.[0]?.properties?.kind;
    if (kind !== "center" && kind !== "radius") return;
    if ("points" in e && e.points.length !== 1) return;
    // Stops the map from also treating this gesture as a pan.
    e.preventDefault();
    dragging = kind;
    map.dragPan.disable();
    canvas.style.cursor = "grabbing";
    map.on("mousemove", onMove);
    map.on("touchmove", onMove);
    map.once("mouseup", stop);
    map.once("touchend", stop);
  };

  map.on("mousedown", EDITOR_HANDLE_LAYER, start);
  map.on("touchstart", EDITOR_HANDLE_LAYER, start);
  map.on("mouseenter", EDITOR_HANDLE_LAYER, () => {
    if (!dragging) canvas.style.cursor = "grab";
  });
  map.on("mouseleave", EDITOR_HANDLE_LAYER, () => {
    if (!dragging) canvas.style.cursor = "";
  });

  map.on("click", SAVED_SPOT_FILL_LAYER, (e) => {
    if (cb.isPicking()) return; // placing a new spot wins over selecting one
    const id = e.features?.[0]?.properties?.id;
    if (typeof id === "string") cb.onSpotClick(id);
  });
  map.on("mouseenter", SAVED_SPOT_FILL_LAYER, () => {
    if (!cb.isPicking() && !dragging) canvas.style.cursor = "pointer";
  });
  map.on("mouseleave", SAVED_SPOT_FILL_LAYER, () => {
    if (!dragging) canvas.style.cursor = cb.isPicking() ? "crosshair" : "";
  });
}

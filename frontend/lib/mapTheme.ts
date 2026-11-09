import type maplibregl from "maplibre-gl";
import type { ThemeName } from "./palette";

const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";

/**
 * Style URL per theme. The light theme reuses the dark style's layer structure
 * (the stock OpenFreeMap "dark" style) and is retinted by lib/basemapStyle.ts,
 * because OpenFreeMap's own light styles use different layer ids. Both can be
 * pointed at another provider through the env vars (see ADR 0004).
 */
export function basemapStyleUrl(dark?: string, light?: string): Record<ThemeName, string> {
  const base = dark || DEFAULT_STYLE_URL;
  return { dark: base, light: light || base };
}

/** Ids of every layer drawn from one of ConnX's own sources (not the basemap's). */
export function customLayerIds(map: maplibregl.Map, sourceIds: readonly string[]): string[] {
  const layers = map.getStyle().layers ?? [];
  return layers
    .filter((l) => "source" in l && sourceIds.includes((l as { source: string }).source))
    .map((l) => l.id);
}

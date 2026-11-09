import type { Theme } from "./palette";

export interface PaintOverride {
  layer: string;
  prop: string;
  value: string | number;
}

const LABEL_LAYERS = [
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
const MAJOR_LABEL_LAYERS = ["place_city", "place_city_large", "place_country_major"];

/**
 * Paint overrides that retint the stock OpenFreeMap style (layer ids from that
 * style) to a theme's basemap tokens. The caller skips ids the loaded style
 * lacks, so a different configured style degrades to "stock".
 */
export function basemapOverrides(theme: Theme): PaintOverride[] {
  const m = theme.basemap;
  const o: PaintOverride[] = [];
  const add = (layer: string, prop: string, value: string | number) => o.push({ layer, prop, value });

  add("background", "background-color", m.background);
  add("water", "fill-color", m.water);
  add("waterway", "line-color", m.water);
  add("landcover_ice_shelf", "fill-color", m.ice);
  add("landcover_glacier", "fill-color", m.ice);
  add("landuse_residential", "fill-color", m.residential);
  add("landuse_residential", "fill-opacity", theme.mapOpacity.residential);
  add("landuse_park", "fill-color", m.park);
  add("landcover_wood", "fill-color", m.park);
  add("building", "fill-color", m.building);
  add("building", "fill-outline-color", m.buildingOutline);

  add("highway_path", "line-color", m.path);
  add("highway_minor", "line-color", m.minorRoad);
  add("highway_major_casing", "line-color", m.roadCasing);
  add("highway_major_inner", "line-color", m.majorRoad);
  add("highway_major_subtle", "line-color", m.majorRoad);
  add("highway_motorway_casing", "line-color", m.roadCasing);
  add("highway_motorway_inner", "line-color", m.motorway);
  add("highway_motorway_subtle", "line-color", m.majorRoad);
  add("aeroway-taxiway", "line-color", m.minorRoad);
  add("aeroway-runway", "line-color", m.majorRoad);
  add("aeroway-runway-casing", "line-color", m.roadCasing);
  add("aeroway-area", "fill-color", m.aeroArea);
  add("road_area_pier", "fill-color", m.majorRoad);
  add("road_pier", "line-color", m.majorRoad);
  for (const id of ["railway", "railway_minor", "railway_transit"]) add(id, "line-color", m.rail);
  for (const id of ["railway_dashline", "railway_minor_dashline", "railway_transit_dashline"]) {
    add(id, "line-color", m.railDash);
  }
  add("boundary_state", "line-color", m.boundaryState);
  add("boundary_country_z0-4", "line-color", m.boundaryCountry);
  add("boundary_country_z5-", "line-color", m.boundaryCountry);

  for (const id of LABEL_LAYERS) {
    const color = id === "water_name" ? m.waterLabel : MAJOR_LABEL_LAYERS.includes(id) ? m.labelMajor : m.label;
    add(id, "text-color", color);
    add(id, "text-halo-color", m.labelHalo);
    add(id, "text-halo-width", 1.5);
    add(id, "text-halo-blur", 0.5);
  }
  return o;
}

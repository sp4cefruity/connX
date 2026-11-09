import { describe, expect, it } from "vitest";
import { basemapOverrides } from "./basemapStyle";
import { THEMES } from "./palette";

describe("basemapOverrides", () => {
  const t = THEMES.dark;
  const find = (layer: string, prop: string) =>
    basemapOverrides(t).find((o) => o.layer === layer && o.prop === prop)?.value;

  it("takes every colour from the theme tokens", () => {
    expect(find("background", "background-color")).toBe(t.basemap.background);
    expect(find("highway_motorway_inner", "line-color")).toBe(t.basemap.motorway);
    expect(find("water_name", "text-color")).toBe(t.basemap.waterLabel);
    expect(find("place_city", "text-color")).toBe(t.basemap.labelMajor);
    expect(find("place_town", "text-color")).toBe(t.basemap.label);
    expect(find("place_town", "text-halo-color")).toBe(t.basemap.labelHalo);
  });

  it("never paints the basemap in a role colour, so roles stay unmistakable", () => {
    const roleColours = Object.values(t.roles).map((r) => r.color.toLowerCase());
    for (const o of basemapOverrides(t)) expect(roleColours).not.toContain(String(o.value).toLowerCase());
  });
});

# 0004 — Vector basemap with light and dark styles

Status: accepted

## Context

The map uses raster Carto dark tiles with a brightness tweak. Raster tiles blur
on zoom, can't be restyled, and make it hard to place route layers under
labels. The product also needs a light/dark toggle.

## Decision

Move to an OpenFreeMap vector basemap (no API key) rendered by the existing
MapLibre GL. Maintain two custom styles, dark and light, tuned to the app
palette. Route, band and marker layers are inserted below the label layers.

The theme defaults to the system preference, is remembered in `localStorage`,
and switches both the UI and the basemap style.

## Consequences

- Two styles to maintain and check for contrast and colour-blind safety.
- Swapping a style at runtime drops custom layers, so layers must be re-added
  on `style.load`.
- Depends on OpenFreeMap's availability. The style URL is configurable, so it
  can be swapped for another provider.

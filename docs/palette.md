# Palette

Ticket 08. Source of truth: `frontend/lib/palette.ts`. The checks below run as
tests (`npm test`, `frontend/lib/palette.test.ts`) for every theme in `THEMES`,
so they keep holding when a colour changes.

## Roles (dark theme; the light theme keeps the same five roles, see below)

| Role | Colour | Drawn as | Where |
|---|---|---|---|
| Route A (yours) | `#5EE6C4` teal | 4 px line with glow | map, "Your route" dot |
| Route B (to avoid) | `#B98CFF` violet | 5 px line | map, "Route to avoid" dot |
| Overlap | `#F64DA6` magenta | 7 px solid line, full opacity | map, overlap figures, flag dots |
| Encounter | `#F5C24B` amber | dot with gap label | map, Close passes panel |
| Red zone | `#FF5A36` orange-red | translucent area, dashed outline; solid when Route A hits it | band around Route B, red spots, Red spots panel |

Overlap used to share the red-zone orange. They are now two colours. Red zone is
the only role that is an area; overlap is the only wide solid line; encounter is
the only dot. Non-role UI colours are `accent` (teal, focus and primary buttons)
and `danger` (error text). Neither is drawn on the map.

## How tokens reach the UI and the map

`lib/palette.ts` holds each theme as plain data. `themeCss()` turns it into CSS
variables (`--c-route-a: 94 230 196`), injected by `app/layout.tsx`.
`tailwind.config.ts` maps class names (`bg-route-a`, `text-overlap`,
`border-border`) to those variables, so the panel never has a hex of its own.
`MapView.tsx` imports the same tokens for its layers, and
`lib/basemapStyle.ts` retints the OpenFreeMap style from the theme's `basemap`
tokens.

**Adding the light theme (ticket 09):** add `"light"` to `THEME_NAMES` and a
`Theme` object to `THEMES`. `themeCss()` emits a `[data-theme="light"]` block,
the tests run over it, and no component changes. A light basemap will need its
own `mapOpacity` values, which are per theme for that reason.

## Checks and thresholds

Method: the dataviz skill (OKLab distance x100, Machado 2009 colour-vision
simulation at severity 1.0, thresholds calibrated to it). Ported in
`lib/colourMath.ts`, with tests against the reference validator's numbers.

| Check | Threshold | Applies to |
|---|---|---|
| Text contrast | >= 4.5:1 (WCAG AA) | ink, ink-dim, ink-faint, accent, danger and every role colour, on bg, panel and panel-2; text on each role fill; basemap labels on their halo |
| Map mark contrast | >= 3:1 | each role, **as drawn** (at its map opacity), over water, park, buildings, every road class, the red-zone band; red spot outlines over roads |
| Role separation, normal vision | dE >= 15, all 10 pairs | roles |
| Role separation, protan and deutan | dE >= 8; 6 to 8 only if the two roles are drawn with different marks; below 6 fails | roles, all pairs (any two can touch on a map) |
| Role separation, tritan | dE >= 8, or different marks | roles |
| Chroma | OKLCH C >= 0.10 (reads as a colour) | roles |

### Measured (dark)

Contrast of the role colour against the background, and against the lightest
road (motorway) at drawn opacity: A 12.8 / 7.3, B 7.8 / 3.6, overlap 6.1 / 3.8,
encounter 11.9 / 7.4, red zone 6.4 / 3.7.

Role pairs, dE x100 (normal / protan / deutan / tritan). Weakest pairs:

| Pair | Normal | Protan | Deutan | Tritan |
|---|---|---|---|---|
| overlap vs red zone | 15.2 | 16.8 | 14.1 | **4.0** |
| A vs encounter | 19.1 | 14.0 | 14.1 | 23.6 |
| B vs overlap | 18.2 | 14.8 | 13.4 | 21.9 |
| B vs encounter | 31.6 | 30.8 | 31.3 | 14.3 |

Every pair clears 8 under protan and deutan, the common deficiencies. The one
collapse is overlap vs red zone under tritan (about 4, rare). It is fixed with a
second cue: solid wide line against translucent area with a dashed outline
(`mark` in the tokens, enforced by the test).

## Light theme roles

| Role | Dark | Light |
|---|---|---|
| Route A | `#5EE6C4` teal | `#007C46` green |
| Route B | `#B98CFF` violet | `#7A45E0` violet |
| Overlap | `#F64DA6` magenta | `#BE1480` magenta |
| Encounter | `#F5C24B` amber | `#0868B0` blue |
| Red zone | `#FF5A36` orange-red | `#C43510` red-orange |

Light roles must reach 4.5:1 on the pale panels, which makes yellow and bright teal impossible. Amber and teal were replaced by blue and green; amber on white could not stay apart from red-orange for protan and deutan. Same checks and thresholds as dark, same marks. Weak spots (all carry different marks): Route A vs overlap under deutan (6.6), Route A vs red zone under protan (about 8.6), Route A vs encounter under tritan (about 3). Route A vs Route B, which share a mark, is 10 under tritan. Route B line opacity is 0.95 and the path colour is lighter so Route B clears 3:1 over paths and the hit-spot fill. The basemap also retints `aeroway-runway-casing`, `road_pier` and `road_area_pier` now (stock grey otherwise).

## What changed from the first palette

- Overlap `#FF5A36` to `#F64DA6`. It was the same colour as the red zone; no
  orange-red variant stayed apart from the red zone for all three deficiency types.
- Overlap line opacity 0.92 to 1, because at 0.92 it fell below 3:1 over motorways.
- Motorway `#33375A` to `#2F3354` (darker), for the same reason. Other roads unchanged.
- Red spot outline opacity 0.55 to 0.85 (the dashed outline was under 3:1 over roads).
- Placeholder text `#565B6E` to `#7E849A`; water labels `#4C5A7A` to `#6E7EA6`.
  Both were under 4.5:1.
- Compare button and focus rings use `accent`, no longer Route B's violet, so a
  role colour only ever means its role.
- Flag dots in the results cards follow the roles (overlap, red zone); "none" is grey.

## Limits

- Not looked at in a browser. Contrast is computed against the style's tokens;
  the actual rendered map (label placement, glow, the band stacked with spots)
  has not been seen.
- Tritan is checked against the same thresholds as protan and deutan, which are
  calibrated for those two. Treat tritan numbers as indicative.
- The landing page's grid lines (`#191c2b`) are decoration and not a token.

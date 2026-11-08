# ConnX — Product Requirements Document

Status: draft v1 · Terms are defined in [`CONTEXT.md`](../CONTEXT.md).

## 1. Problem

Two people want to travel without running into each other. Existing map apps
answer "how do I get from X to Y", not "where will my route meet theirs, and
how close will we pass".

## 2. Goals

1. Compare two routes and show **how much they overlap** and **where they come
   close** (Encounters), around a user-chosen danger distance.
2. Let the user draw **Red spots** (e.g. someone's house) that their route
   should stay out of.
3. Polish the product to portfolio quality: a refined map, fast search, a good
   palette, light and dark themes, and a responsive layout.
4. Everything runs locally and works end to end.

## 3. Non-goals

- Hosting and deployment (future work).
- Accounts, sharing, cross-device sync, payments, scaling work.
- Time: departure times, speeds and "could meet at the same time" logic.
- Freeform polygon zones and shrinking zones.
- Browser end-to-end test suite.

## 4. Users

Pairs of people (including the two builders) who want to avoid each other's
paths. The tool is used by one person at a time, who enters both trips.

## 5. Core user flow

1. The user picks a travel mode (driving, walking or cycling).
2. The user enters Route A (start, end) and Route B (start, end) via search.
3. The user sets the danger distance (default 200 m).
4. ConnX shows both routes, the overlap, the Red zone band around B, and
   Encounter markers.
5. The side panel summarises overlap and lists Encounters. Clicking one zooms
   the map to it.
6. Optionally, the user draws Red spots; Route A hits are flagged.
7. Optionally, the user asks for a **Recommendation**, an alternative A that
   scores better.

## 6. Functional requirements

### 6.1 Route comparison
- FR1. Compute Route A and Route B for the same travel mode.
- FR2. Overlap uses a fixed tolerance of ~25 m. It reports distance,
  percentage of A, and position along A. The existing sliver-drop and
  segment-merge rules stay.
- FR3. Spatial only; no time inputs.

### 6.2 Danger distance, band and Encounters
- FR4. Danger distance slider: 50 m–1 km, default 200 m. It replaces the
  `sensitivity` presets in API and UI.
- FR5. Draw a Red zone band of that width around Route B.
- FR6. Detect Encounters: contiguous stretches of A within the danger distance
  of B, excluding Overlap stretches. Each yields one marker at its closest
  point and the minimum gap in metres.
- FR7. List Encounters ordered along A; selecting one zooms to it.
- FR8. A new backend service computes Encounters (pure Python/Shapely, like
  `overlap.py`) and is exposed on the compare response.

### 6.3 Red spots (drawn zones)
- FR9. Circles only. Click to place a centre; drag or use a slider to size
  (50 m–2 km).
- FR10. Name, move, resize, delete.
- FR11. Checked against Route A only. Hits are shown on the map and in the
  panel.
- FR12. Persisted per anonymous cookie user. No accounts.

### 6.4 Recommendation (secondary)
- FR13. Keep `/recommend`. Scoring gains an encounter term and uses the danger
  distance. Red spot hits stay in the score.
- FR14. Explanations cover encounters ("2 close passes, nearest 60 m").
- FR15. The comparison view is the primary UI; Recommendation is secondary.

### 6.5 Travel modes
- FR16. Driving, walking and cycling, each served by its own OSM routing
  endpoint (ADR 0002). Both routes share the mode.
- FR17. Verify that walking and cycling return distinct, correct routes. The
  public OSRM demo probably returned driving routes for all three.

### 6.6 Search
- FR18. Photon is the primary geocoder, biased to the map viewport. On
  timeout or error, fall back to Nominatim (ADR 0003).
- FR19. Short-TTL in-memory cache in front of both providers.
- FR20. If both are slow, show a quiet "search is slow right now" state.

### 6.7 Map
- FR21. OpenFreeMap vector basemap rendered by MapLibre, with custom dark and
  light styles (ADR 0004).
- FR22. Route, band and marker layers sit below the labels and survive theme
  switches.

### 6.8 Look and feel
- FR23. Role-based palette: Route A, Route B, Overlap, Encounter and Red zone,
  each distinct. Checked for contrast and colour-blind safety in both themes.
- FR24. Dark and light themes with a toggle. The default follows the system
  preference; the choice persists in `localStorage`.
- FR25. Responsive layout: side panel on desktop, bottom sheet on mobile.
- FR26. Real empty, loading and error states throughout.

## 7. API changes

- `POST /api/routes/compare`: drop `sensitivity`; add `danger_distance_m`.
  Response adds `encounters[]` (location, min gap in metres, position along
  A) alongside `overlap`.
- `POST /api/routes/recommend`: same request change; each scored route
  includes its encounters; scoring adds an encounter term.
- `GET /api/geocode`: accepts optional viewport bias (`lat`, `lon`).
- Config: per-mode routing base URLs; Photon base URL; fixed overlap
  tolerance (~25 m); remove `overlap_sensitivity_presets`.

## 8. Acceptance criteria

1. A driving comparison between two real city routes shows overlap, the
   Red zone band, Encounter markers with metre gaps, and a zoomable list.
2. Changing the danger distance updates the band and Encounters, and does not
   change the overlap result.
3. Walking and cycling return plausibly different routes from driving.
4. A drawn Red spot on A's path flags a hit; one off the path does not.
   Spots survive a page reload.
5. Search results appear noticeably faster than before and fall back cleanly
   when Photon is unavailable.
6. Dark and light themes both render map and UI correctly, and the toggle
   persists.
7. The planner is usable at mobile width.
8. `pytest` passes, including new Encounter tests plus updated overlap and
   scoring tests; `next build` and lint pass.
9. The README has screenshots (dark, plus one light) and setup steps that
   work.

## 9. Testing and Definition of Done

- Backend: pytest for the Encounter service (clustering, closest point,
  overlap exclusion, threshold edges) and for the changed overlap and scoring
  behaviour.
- Frontend: `next build` and lint pass.
- Manual: run all three modes in the browser, in both themes.
- README with screenshots. No browser E2E suite.

## 10. Suggested delivery order

1. Backend: fixed overlap tolerance, danger distance, Encounter service,
   schema changes, tests.
2. Routing: per-mode servers and verification (FR16–17).
3. Search: Photon, fallback, cache, viewport bias.
4. Frontend map: vector basemap, band, markers, Encounter list.
5. Red spot drawing UX (place, resize, edit).
6. Palette, themes and toggle, responsive layout, empty and error states.
7. Recommendation scoring update.
8. README, screenshots, final manual pass.

## 11. Risks and open items

- Public routing and geocoding servers are fair-use with no SLA, which is
  fine for a demo and a risk for anything more.
- OpenFreeMap availability and style quality. The style URL is configurable.
- Switching map styles at runtime drops custom layers and needs re-adding.
- Whether the public OSRM demo truly ignores the profile is unverified. FR17
  covers it.
- Anonymous cookie users lose Red spots if cookies are cleared. This is
  accepted.

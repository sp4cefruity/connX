# 0007 — Self-hosted Valhalla routing

Status: parked — code kept on disk but not wired in; ORS (ADR 0005) is the active provider

## Context

Hosted routing is rationed. OpenRouteService (ADR 0005) allows 2,000 directions
a day, caps alternatives at ~100 km and avoid areas at 20 km across, and `/recommend`
spends several calls per search. Public OSRM (ADR 0002) has no SLA and cannot
route around an area, so Recommend's avoid-Route-B step (ADR 0006) does nothing
on it. The first target region is eastern India (Odisha), which a single
OpenStreetMap extract covers.

## Decision

- Add `routing/valhalla.py`, a `ValhallaRouting` backend for the existing
  routing contract. It POSTs to Valhalla's `/route` with costing `auto`,
  `pedestrian` or `bicycle` per mode. Alternatives use `alternates`, via points
  are `through` locations, and the avoid case sends `exclude_polygons` (outer
  rings of the GeoJSON area). Shapes are decoded from polyline6.
- `ROUTING_PROVIDER=valhalla` builds `FallbackRouting(Cached(Valhalla),
  Cached(OSRM))`, the same chain shape as ORS. Any `RoutingProviderError`
  (Valhalla down, 400 "no suitable edges near location" for a point outside the
  tiles, no path) retries on the public per-mode OSRM servers and is logged.
  The circuit breaker applies as before. Avoid calls have no fallback.
- `VALHALLA_BASE_URL` sets the server: `http://localhost:8002` by default,
  `http://valhalla:8002` in docker compose.
- Valhalla is the default on this branch (`backend/.env.example` and the compose
  backend). ORS stays available and `ORS_API_KEY` is now optional.
- Compose gets a `valhalla` service (`ghcr.io/valhalla/valhalla-scripted`, port
  8002, `./valhalla/custom_files` mounted at `/custom_files`) behind the
  `valhalla` profile, and the backend does not depend on it. `docker compose up`
  still works for people who skip it: the backend falls back to OSRM.
- Tiles come from Geofabrik's India Eastern Zone extract (~236 MiB), used whole,
  not clipped. `scripts/valhalla-setup.sh` downloads it; the image builds tiles
  on first start.
- Geocoding is unchanged (Photon, ADR 0003).

## Consequences

- No quota or rate limit, and real avoid-area detours with no 20 km / 200 km2 /
  150 km caps from ORS. Alternatives are still best-effort, and Valhalla returns
  them for two-point routes only.
- Valhalla caps the total perimeter of exclude polygons
  (`service_limits.max_exclude_polygons_length`, default 10 km). The avoid zone
  along a 13 km shared road has a longer perimeter, so the default would refuse
  it. `scripts/valhalla-setup.sh --limits` raises it in `valhalla.json` after
  the first start. Until then the avoid call fails and Recommend moves on to via
  points (ADR 0006).
- Routes outside the extract (anything beyond eastern India) come from public
  OSRM, with its limits.
- First tile build takes several minutes and a few GB of RAM, and the tiles live
  on disk (git-ignored). Running it is the developer's job; production hosting is
  out of scope.
- Like ORS, results ignore live traffic. Valhalla and OSRM will not give identical
  distances or times for the same trip.
- The compose service, the tile build and the live HTTP calls were not run when
  this was written; only the provider, the fallback chain and the factory are
  covered by tests (mocked HTTP).

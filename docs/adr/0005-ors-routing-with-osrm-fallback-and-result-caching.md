# 0005 — OpenRouteService routing with OSRM fallback and result caching

Status: accepted

## Context

Routing ran on the public OSM OSRM servers (ADR 0002): fair-use, no SLA. We want
a keyed free tier as the primary. OpenRouteService (ORS) gives 2,000 directions
per day and 40 per minute free, and supports alternative routes (max 3, ~100 km
on the hosted API). `/recommend` and `/compare` each make several routing calls,
so that quota is easy to burn.

## Decision

- Add `routing/ors.py`, an `ORSRouting` backend for the existing routing
  contract. `ROUTING_PROVIDER=ors` is the default.
- `FallbackRouting(ORS, OSRM)`: any `RoutingProviderError` (network, 403/429
  quota, no route) retries on the per-mode OSRM servers. With no `ORS_API_KEY`
  the app runs on OSRM alone and logs a warning.
- `CachedRouting` wraps the chain. Key: endpoints rounded to 5 decimals (~1 m),
  mode and count. One hour TTL, 500 entries, successes only.
- One `TTLCache` (LRU + TTL) replaces the ad-hoc dict in the geocode router.
- Providers stay swappable: wrappers know nothing about which backend is inside,
  and the choice is config in `get_routing_provider()`.

## Consequences

- Cache is per process and lost on restart, and not shared between workers.
  Move it to Redis or Postgres if we run several workers.
- Routes ignore live traffic, so a one-hour TTL costs no accuracy.
- ORS alternatives over ~100 km degrade to a single route; the recommender then
  has one candidate.
- Basemap is unchanged: OpenFreeMap (ADR 0004). A Protomaps fallback was
  considered and deferred.

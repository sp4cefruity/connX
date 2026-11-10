# 0006 — Recommend builds its own detour candidates

Status: accepted

## Context

`/recommend` only ranked the alternatives a routing provider returned. OSRM
returns few, ORS returns none above ~100 km (ADR 0005), and the ones it does
return usually share most of their roads. So the list often had a single route
and there was nothing to recommend, even when that route ran straight along
Route B.

## Decision

- Routing providers gain `get_route_via(start, via, end, mode)`: one route
  through a single via point, which the provider snaps to the nearest road.
  OSRM and ORS pass it as an extra coordinate; the cache keys on it; the
  fallback chain treats it like any other call.
- `services/detours.py` is pure geometry. `plan_waypoints` takes the best route
  and its trouble (Overlap segments, Encounters, Red spots it enters) and puts
  one via point beside each stretch, on the side that gets further from what is
  being avoided. The offset is 1.5 x the danger distance (or Red spot radius),
  never under 250 m. Red spots are planned first, then overlap, then the
  closest passes. Via points within one offset of each other share a detour.
- `filter_detours` drops a detour that is >=90% on a road we already have, or
  that takes more than twice the fastest route's time.
- **Avoid zone first.** Providers also gain `get_route_avoiding(start, end,
  mode, area)`. Only ORS implements it (`options.avoid_polygons`); OSRM and the
  mock refuse. `build_avoid_zone` makes the area: a 40 m strip along Route B's
  road beside each shared stretch (padded 150 m along A), plus the Red spots the
  route enters. One call replaces the guesswork of via points. ORS caps avoid
  areas at 20 km across, 200 km2 and 150 km routes, so a zone over 19 km
  across is not sent, and any provider error just moves on to via points. On
  the Cuttack corridor below the zone is 2.0 x 13.5 km, 1.2 km2.
  A "no route avoids this" answer does not count against the circuit breaker;
  a quota refusal does. There is no OSRM fallback for it.
- A detour must also **improve on the route it detours around** (`improves_on`):
  fewer Red spots, fewer close passes, or at most 80% of the shared km, and
  never more Red spots or over 105% of the shared km. Without this, a longer
  route that shares the same road looks better, because scoring penalises
  overlap *percentage* and the extra distance dilutes it. Seen live on OSRM
  (Bhubaneswar → Cuttack, 14.22 km shared; a one-via detour shared 14.35 km
  but scored better, 47.8% against 52.3%).
- `/recommend` runs this only when the provider returned fewer routes than
  `alternatives_count` **and** the best route has something the user asked to
  avoid. It tries the avoid zone (one call); if that gives nothing better it
  tries via points, at most `min(3, alternatives_count - routes_found)` calls in
  parallel. Detours are scored and ranked with the provider's candidates, so the
  response schema is unchanged.
- **Scoring measures overlap in km, not percent of the route.** The penalty is
  the shared km as a percentage of the *shortest* candidate, so extra distance
  can no longer dilute it. This applies to the provider's own alternatives too.
- When no detour survives, the recommended route's explanation says "No better
  route found nearby" rather than leaving a single route unexplained.

## Consequences

- A click can cost up to 4 more routing calls (the avoid zone, then 3 via
  points; ORS free tier: 2,000 a day). The route cache absorbs repeats of the
  same trip. On OSRM alone the avoid call is refused locally, without a
  request, so only the via points cost anything.
- The avoid-zone path is written against ORS's documented API and tested with a
  mock server. It has not been run against live ORS (no key was available).
- A detour only exists if there is a road on the far side. In a one-road
  corridor the result is still a single route, now with that explanation line.
- The via point is a guess: the router may snap it back onto the shared road.
  Those detours are dropped as duplicates instead of being shown.
- Each trouble stretch gets one via point, however long it is. On a long shared
  highway that does not work: the router goes out to the point and rejoins the
  same road. Probed live on that same pair, one via point shared 14.35 to 15.37
  km (original 14.22 km); three points 1,500 m off shared 7.83 km but cost 19 km
  and 45 minutes more. Those detours are now rejected. With ORS the avoid zone
  handles this case; on OSRM alone such trips report "No better route found
  nearby", because OSRM cannot be told about Route B.

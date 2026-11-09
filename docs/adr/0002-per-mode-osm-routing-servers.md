# 0002 — Per-mode OSM routing servers

Status: accepted

## Context

`routing/osrm.py` builds `/route/v1/{foot|bike|driving}/…` against
`router.project-osrm.org`. The public OSRM demo is believed to serve only the
car profile regardless of the path profile, so walking and cycling likely
return driving routes. This must be verified during implementation.
Verified: an OSRM server bakes in one profile and ignores the profile segment of
the URL, so the mode must be chosen by the server (base URL), not the path.

## Decision

Keep driving, walking and cycling. Route each mode to its dedicated OSM
server (`routing.openstreetmap.de/routed-car`, `/routed-foot`, `/routed-bike`),
configured per mode. Both routes in a comparison share one mode. The
`RoutingProvider` interface is unchanged.

## Consequences

- Base URLs become per-mode settings with sensible defaults.
- These are still public, fair-use servers, which is fine for a demo and not
  for production traffic. Self-hosting remains the future path.
- The mock provider stays for offline dev and tests.

# 0003 — Photon for search, Nominatim as fallback

Status: accepted

## Context

Search is slow. The public Nominatim instance is limited to ~1 request/second
and is not built for type-ahead.

## Decision

Add a Photon geocoding provider behind the existing geocoder interface:

- Photon is the primary provider for forward search, biased to the current map
  viewport.
- On timeout or error, fall back automatically to Nominatim.
- Nominatim stays the reverse-geocoder.
- A short-TTL in-memory cache sits in front of both.
- If both are slow, show a quiet "search is slow right now" state rather than
  an error.

No API keys are required.

## Consequences

- Photon's public server is fair-use with no SLA, hence the fallback.
- The frontend sends viewport bias (lat/lon) with search requests.
- Debounce can be tightened once the backend is fast.

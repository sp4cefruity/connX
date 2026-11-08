# 0001 — Separate overlap tolerance from danger distance

Status: accepted

## Context

Today one `sensitivity` preset (20/50/100 m) sets the corridor used for
overlap. "Overlap" and "how close do the routes come" are therefore the same
measurement, so there is no way to report near-misses that are not shared
road.

## Decision

Two distinct numbers:

- **Overlap tolerance**: fixed, ~25 m. Means "same road".
- **Danger distance**: user-set slider, 50 m–1 km, default 200 m. Drives the
  Red zone band and the Encounter threshold.

The `sensitivity` presets are removed from the API and UI.

## Consequences

- Encounters exclude Overlap stretches, so the two results don't double count.
- The compare/recommend request schemas change (breaking, acceptable: no
  external API consumers).
- Scoring gains an encounter term driven by danger distance.

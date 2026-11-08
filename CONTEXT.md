# ConnX — Domain Context

ConnX helps two people travel without running into each other. You enter two
trips, and ConnX shows where they share road and where they come close.

This file is the shared vocabulary. Use these terms in code, UI copy and docs.

## Glossary

**Route A** — The user's own trip (start → end). Everything is judged from
A's point of view: "where does *my* route meet theirs".

**Route B** — The other person's trip (start → end). Entered by the user;
never stored.

**Travel mode** — driving, walking or cycling. One mode applies to both
routes in a comparison.

**Overlap** — A stretch where A runs on (effectively) the same road as B,
measured with a small fixed tolerance (~25 m). Reported as distance,
percentage of A, and position along A. Slivers shorter than the minimum
meaningful length are dropped; segments a few metres apart are merged.

**Danger distance** — The single user-set distance (50 m–1 km, default
200 m) within which B is considered too close. It sets the width of the
Red zone band and the threshold for Encounters. Not the same number as the
overlap tolerance.

**Red zone band** — The translucent band of width *danger distance* drawn
around Route B. The survival-game "red zone": the area you don't want to be
in.

**Encounter** — A contiguous stretch of A that lies inside the Red zone band
but is not Overlap. Reported as one marker at its closest point, with the
minimum gap in metres. Ordered along A.

**Red spot** — A user-drawn circle (centre + radius, 50 m–2 km, named, e.g.
"Priya's house") that Route A should stay out of. Checked against Route A
only. Persisted per anonymous cookie user. Also called a "drawn red zone"
in conversation; "Red spot" is the code name (`SavedLocation`).

**Red spot hit** — Route A passes within a Red spot's radius.

**Recommendation** — A secondary feature: fetch alternative candidates for
Route A and rank them by a score that weighs time, distance, overlap,
encounters and Red spot hits. Lower score is better.

**Anonymous user** — An opaque id in a cookie. No email, no password, no
sharing. Owns Red spots.

## Principles

- **Spatial only.** Time and departure schedules are out of scope.
- **Privacy-first.** Trips are computed on demand and not stored. Only Red
  spots (which the user created) are persisted.
- **A's perspective.** Overlap and Encounters are measured along A.

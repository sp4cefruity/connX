"""
Route scoring (spec §14): rank alternative routes by a weighted mix of
overlap, red-zone violations, travel time, and distance — not just raw
speed. Lower score = better.

    total = time_penalty + overlap_penalty + red_zone_penalty + distance_penalty

Weights are deliberately lopsided: overlap and red zones dominate unless
the user turns them off (spec §29 "Avoidance Mode"), because the whole
point of the product is "best route that minimises unwanted encounters
while remaining reasonably efficient" (spec §14), not shortest-path.
"""
from dataclasses import dataclass

from app.schemas import OverlapResult, RedSpotHit, RouteResult, RouteScoreBreakdown

# Tunable weights. Red zones dominate; overlap is next; time and
# distance are moderate/low as specified in §14.
W_TIME_PER_MIN = 1.0
W_OVERLAP_PER_PERCENT = 4.0
W_RED_ZONE_HIT = 250.0
W_DISTANCE_PER_KM = 0.5


@dataclass
class ScoringInputs:
    route: RouteResult
    overlap: OverlapResult
    red_spot_hits: list[RedSpotHit]
    avoid_overlap: bool
    avoid_red_spots: bool
    fastest_duration_min: float
    shortest_distance_km: float


def score_route(inp: ScoringInputs) -> RouteScoreBreakdown:
    time_penalty = round((inp.route.duration_min - inp.fastest_duration_min) * W_TIME_PER_MIN, 2)
    time_penalty = max(time_penalty, 0.0)

    distance_penalty = round((inp.route.distance_km - inp.shortest_distance_km) * W_DISTANCE_PER_KM, 2)
    distance_penalty = max(distance_penalty, 0.0)

    overlap_penalty = 0.0
    if inp.avoid_overlap:
        overlap_penalty = round(inp.overlap.percentage * W_OVERLAP_PER_PERCENT, 2)

    red_zone_penalty = 0.0
    if inp.avoid_red_spots:
        hits = sum(1 for h in inp.red_spot_hits if h.intersects)
        red_zone_penalty = round(hits * W_RED_ZONE_HIT, 2)

    total = round(time_penalty + overlap_penalty + red_zone_penalty + distance_penalty, 2)

    return RouteScoreBreakdown(
        time_penalty=time_penalty,
        overlap_penalty=overlap_penalty,
        red_zone_penalty=red_zone_penalty,
        distance_penalty=distance_penalty,
        total=total,
    )


def explain(route: RouteResult, overlap: OverlapResult, red_spot_hits: list[RedSpotHit], fastest: RouteResult) -> list[str]:
    """Human-readable "why this route" lines (spec §35)."""
    lines = []

    delta_min = round(route.duration_min - fastest.duration_min, 1)
    if delta_min <= 0:
        lines.append("Fastest option available")
    else:
        lines.append(f"{delta_min:g} min slower than the fastest route")

    if overlap.percentage == 0:
        lines.append("No overlap with the route you're avoiding")
    else:
        lines.append(f"{overlap.percentage:g}% overlap with the route you're avoiding")

    hit_names = [h.red_spot.name for h in red_spot_hits if h.intersects]
    if hit_names:
        lines.append(f"Enters: {', '.join(hit_names)}")
    else:
        lines.append("Avoids all red spots")

    return lines

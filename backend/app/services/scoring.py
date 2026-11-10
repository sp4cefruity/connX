"""
Route scoring (spec §14): rank alternative routes by a weighted mix of
overlap, encounters (close passes), red-zone violations, travel time, and
distance — not just raw speed. Lower score = better.

    total = time_penalty + overlap_penalty + encounter_penalty
            + red_zone_penalty + distance_penalty

Weights are deliberately lopsided: overlap and red zones dominate unless
the user turns them off (spec §29 "Avoidance Mode"), because the whole
point of the product is "best route that minimises unwanted encounters
while remaining reasonably efficient" (spec §14), not shortest-path.
"""
from dataclasses import dataclass, field

from app.schemas import (
    DANGER_DISTANCE_DEFAULT_M,
    Encounter,
    OverlapResult,
    RedSpotHit,
    RouteResult,
    RouteScoreBreakdown,
)

# Tunable weights. Red zones dominate; overlap is next; time and
# distance are moderate/low as specified in §14.
W_TIME_PER_MIN = 1.0
W_OVERLAP_PER_PERCENT = 4.0
W_RED_ZONE_HIT = 250.0
W_DISTANCE_PER_KM = 0.5
# Each close pass costs W_ENCOUNTER at the edge of the danger distance, rising
# to 2 * W_ENCOUNTER as the gap shrinks to zero. So fewer passes always beat
# more, and among equal counts the more distant passes win.
W_ENCOUNTER = 10.0


@dataclass
class ScoringInputs:
    route: RouteResult
    overlap: OverlapResult
    red_spot_hits: list[RedSpotHit]
    avoid_overlap: bool
    avoid_red_spots: bool
    fastest_duration_min: float
    shortest_distance_km: float
    encounters: list[Encounter] = field(default_factory=list)
    danger_distance_m: float = DANGER_DISTANCE_DEFAULT_M


def _encounter_penalty(encounters: list[Encounter], danger_distance_m: float) -> float:
    penalty = 0.0
    for e in encounters:
        closeness = 1 - e.min_gap_m / danger_distance_m
        penalty += W_ENCOUNTER * (1 + min(max(closeness, 0.0), 1.0))
    return round(penalty, 2)


def _overlap_percent(inp: ScoringInputs) -> float:
    """Shared road as a percentage of the *shortest* candidate, not of this route.

    Measured against the route's own length, extra distance dilutes the
    percentage: a 30 km detour sharing the same 14 km with Route B would look
    better than the 27 km original. Measured against one fixed length, sharing
    more road always costs more, and sharing the same road costs the same.
    """
    if inp.shortest_distance_km <= 0:
        return inp.overlap.percentage
    return inp.overlap.distance_km / inp.shortest_distance_km * 100


def score_route(inp: ScoringInputs) -> RouteScoreBreakdown:
    time_penalty = round((inp.route.duration_min - inp.fastest_duration_min) * W_TIME_PER_MIN, 2)
    time_penalty = max(time_penalty, 0.0)

    distance_penalty = round((inp.route.distance_km - inp.shortest_distance_km) * W_DISTANCE_PER_KM, 2)
    distance_penalty = max(distance_penalty, 0.0)

    overlap_penalty = 0.0
    if inp.avoid_overlap:
        overlap_penalty = round(_overlap_percent(inp) * W_OVERLAP_PER_PERCENT, 2)

    # Close passes are part of avoiding Route B, so the same toggle covers them.
    encounter_penalty = 0.0
    if inp.avoid_overlap:
        encounter_penalty = _encounter_penalty(inp.encounters, inp.danger_distance_m)

    red_zone_penalty = 0.0
    if inp.avoid_red_spots:
        hits = sum(1 for h in inp.red_spot_hits if h.intersects)
        red_zone_penalty = round(hits * W_RED_ZONE_HIT, 2)

    total = round(
        time_penalty + overlap_penalty + encounter_penalty + red_zone_penalty + distance_penalty, 2
    )

    return RouteScoreBreakdown(
        time_penalty=time_penalty,
        overlap_penalty=overlap_penalty,
        encounter_penalty=encounter_penalty,
        red_zone_penalty=red_zone_penalty,
        distance_penalty=distance_penalty,
        total=total,
    )


def _format_m(metres: float) -> str:
    """"60 m" up to 999 m, then "1 km" / "1.2 km" (matches the frontend's formatGap)."""
    if metres < 999.5:
        return f"{round(metres)} m"
    return f"{metres / 1000:.1f}".rstrip("0").rstrip(".") + " km"


def _close_passes_line(encounters: list[Encounter], danger_distance_m: float) -> str:
    if not encounters:
        return f"No close passes within {_format_m(danger_distance_m)}"
    nearest = _format_m(min(e.min_gap_m for e in encounters))
    if len(encounters) == 1:
        return f"1 close pass, {nearest} away"
    return f"{len(encounters)} close passes, nearest {nearest}"


def explain(
    route: RouteResult,
    overlap: OverlapResult,
    red_spot_hits: list[RedSpotHit],
    fastest: RouteResult,
    encounters: list[Encounter] | None = None,
    danger_distance_m: float = DANGER_DISTANCE_DEFAULT_M,
) -> list[str]:
    """Human-readable "why this route" lines (spec §35).

    `encounters` is None when there is no route to avoid; then the close
    passes line is left out rather than claiming there are none.
    """
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

    if encounters is not None:
        lines.append(_close_passes_line(encounters, danger_distance_m))

    hit_names = [h.red_spot.name for h in red_spot_hits if h.intersects]
    if hit_names:
        lines.append(f"Enters: {', '.join(hit_names)}")
    else:
        lines.append("Avoids all red spots")

    return lines

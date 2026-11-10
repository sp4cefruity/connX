"""
Detour planning for "recommend a better route".

The routing providers return few alternatives (often one), and all of them tend
to share the same roads. So when the best route still has trouble on it (shared
road with Route B, close passes, Red spots it enters) we make our own
candidates: pick a via point beside each trouble stretch, on the side away from
what we are avoiding, and route start -> via -> end. The router snaps the via
point to the nearest road. Scoring then decides whether the detour is worth it.

This module is pure geometry: no network, no DB. Everything is done in the local
metric plane (see projection.py).
"""
from dataclasses import dataclass

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from app.schemas import Encounter, LonLat, OverlapResult, RouteResult
from app.services.overlap import compute_overlap
from app.services.projection import Projection, mean_lat

# The via point sits this many danger distances (or Red spot radii) off the
# route, but never closer than the floor: a point 75 m off a road would simply
# snap back onto it.
OFFSET_FACTOR = 1.5
MIN_OFFSET_M = 250.0

# Step used to read the route's local direction.
_DIRECTION_STEP_M = 5.0

# A detour is dropped when this much of it runs on a road we already have, or
# when it takes more than this many times the fastest route's time.
DUPLICATE_OVERLAP_PCT = 90.0
MAX_DURATION_RATIO = 2.0

# Planning order: Red spots first (hardest constraint), then shared road, then
# close passes.
_PRIORITY_RED_SPOT = 0
_PRIORITY_OVERLAP = 1
_PRIORITY_ENCOUNTER = 2


@dataclass(frozen=True)
class AvoidCircle:
    """A Red spot the route enters."""

    lon: float
    lat: float
    radius_m: float


@dataclass(frozen=True)
class _Stretch:
    priority: int
    severity: float  # larger = planned earlier within a priority
    along_m: float  # where on the route, in metres from its start
    avoid: BaseGeometry  # what the detour must get away from
    offset_m: float


def _offset(distance_m: float) -> float:
    return max(OFFSET_FACTOR * distance_m, MIN_OFFSET_M)


def _normal_at(route: LineString, along_m: float) -> tuple[float, float] | None:
    """Unit vector perpendicular to the route at `along_m`, or None if it has no direction."""
    lo = max(along_m - _DIRECTION_STEP_M, 0.0)
    hi = min(along_m + _DIRECTION_STEP_M, route.length)
    a, b = route.interpolate(lo), route.interpolate(hi)
    dx, dy = b.x - a.x, b.y - a.y
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return None
    return -dy / length, dx / length


def _via_point(route: LineString, trouble: _Stretch) -> Point | None:
    normal = _normal_at(route, trouble.along_m)
    if normal is None:
        return None
    here = route.interpolate(trouble.along_m)
    sides = [
        Point(here.x + normal[0] * trouble.offset_m, here.y + normal[1] * trouble.offset_m),
        Point(here.x - normal[0] * trouble.offset_m, here.y - normal[1] * trouble.offset_m),
    ]
    # The side that gets further from what we are avoiding.
    return max(sides, key=trouble.avoid.distance)


@dataclass(frozen=True)
class Trouble:
    """How much a route has of what the user asked to avoid."""

    shared_km: float  # road shared with Route B
    close_passes: int  # Encounters with Route B
    red_spot_hits: int  # Red spots entered


# A detour has to share clearly less road with B to count as better. A route
# padded with extra distance can shave the overlap *percentage* while sharing
# the same km, and a via point beside a long shared road usually just snaps
# back onto it.
SHARED_KM_REQUIRED_RATIO = 0.8
SHARED_KM_REGRESSION_RATIO = 1.05


def improves_on(detour: Trouble, baseline: Trouble) -> bool:
    """Does the detour actually get away from what the baseline runs into?

    It must do better on at least one count (fewer Red spots, fewer close
    passes, or clearly less shared road) without getting worse on Red spots or
    the shared road. Scoring then weighs the trade-offs.
    """
    if detour.red_spot_hits > baseline.red_spot_hits:
        return False
    if detour.shared_km > baseline.shared_km * SHARED_KM_REGRESSION_RATIO:
        return False
    return (
        detour.red_spot_hits < baseline.red_spot_hits
        or detour.close_passes < baseline.close_passes
        or detour.shared_km <= baseline.shared_km * SHARED_KM_REQUIRED_RATIO
    )


def filter_detours(
    detours: list[RouteResult],
    existing: list[RouteResult],
    tolerance_m: float,
    min_meaningful_overlap_m: float,
    merge_gap_m: float,
) -> list[RouteResult]:
    """Keep only detours worth showing: not a repeat of a route we already have
    (or of an earlier detour), and not absurdly slow."""
    if not existing:
        return list(detours)

    fastest = min(r.duration_min for r in existing)
    kept: list[RouteResult] = []
    for detour in detours:
        if detour.duration_min > fastest * MAX_DURATION_RATIO:
            continue
        duplicate = any(
            compute_overlap(
                route_a_geometry=detour.geometry,
                route_a_duration_min=detour.duration_min,
                route_b_geometry=other.geometry,
                tolerance_m=tolerance_m,
                min_meaningful_overlap_m=min_meaningful_overlap_m,
                merge_gap_m=merge_gap_m,
            ).percentage
            >= DUPLICATE_OVERLAP_PCT
            for other in [*existing, *kept]
        )
        if not duplicate:
            kept.append(detour)
    return kept


def plan_waypoints(
    route: list[LonLat],
    avoid_route: list[LonLat] | None,
    avoid_circles: list[AvoidCircle],
    danger_distance_m: float,
    overlap: OverlapResult,
    encounters: list[Encounter],
    max_waypoints: int = 3,
) -> list[LonLat]:
    """Via points for detours around the trouble on `route`, most important first.

    `avoid_route` is Route B (None when there is none to avoid). Trouble
    stretches whose via points would land within one offset of an already
    chosen one are skipped: a single detour covers them both.
    """
    if len(route) < 2 or max_waypoints < 1:
        return []

    proj = Projection(ref_lat=mean_lat(route))
    line = LineString(proj.to_xy(route))
    if line.length == 0:
        return []

    troubles: list[_Stretch] = []

    for circle in avoid_circles:
        centre = Point(proj.to_xy([LonLat(lon=circle.lon, lat=circle.lat)])[0])
        troubles.append(
            _Stretch(
                _PRIORITY_RED_SPOT,
                circle.radius_m,
                line.project(centre),
                centre,
                _offset(circle.radius_m),
            )
        )

    if avoid_route and len(avoid_route) >= 2:
        b_line = LineString(proj.to_xy(avoid_route))
        for seg in overlap.segments:
            mid = (seg.start_fraction + seg.end_fraction) / 2
            troubles.append(
                _Stretch(
                    _PRIORITY_OVERLAP,
                    seg.distance_m,
                    mid * line.length,
                    b_line,
                    _offset(danger_distance_m),
                )
            )
        for enc in encounters:
            mid = (enc.start_fraction + enc.end_fraction) / 2
            troubles.append(
                _Stretch(
                    _PRIORITY_ENCOUNTER,
                    -enc.min_gap_m,  # the closer the pass, the earlier
                    mid * line.length,
                    b_line,
                    _offset(danger_distance_m),
                )
            )

    troubles.sort(key=lambda t: (t.priority, -t.severity))

    chosen: list[tuple[Point, float]] = []
    for trouble in troubles:
        if len(chosen) >= max_waypoints:
            break
        point = _via_point(line, trouble)
        if point is None:
            continue
        if any(point.distance(other) < trouble.offset_m for other, _ in chosen):
            continue
        chosen.append((point, trouble.offset_m))

    return [proj.to_lonlat([(p.x, p.y)])[0] for p, _ in chosen]

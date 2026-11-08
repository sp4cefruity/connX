"""
Encounters (CONTEXT.md): contiguous stretches of route A that come within the
danger distance of route B without sharing the road.

Approach:
  1. Project both routes into the local metric plane (projection.py).
  2. Intersect route A with route B buffered by the danger distance (the same
     width as the red zone band).
  3. Express each stretch as a range of distance-along-A and merge stretches
     that are only a few metres apart, so one close pass is one Encounter.
  4. Subtract the Overlap segments, so Overlap and Encounters never count the
     same stretch of road twice.
  5. Per remaining stretch, find the point closest to route B: that is where
     the marker goes and what the minimum gap is measured at.

Pure Python/Shapely, no DB or network, like overlap.py.
"""
from shapely.geometry import LineString
from shapely.ops import nearest_points, substring

from app.schemas import Encounter, LonLat, OverlapSegment
from app.services.linework import as_linestrings, merge_ranges, ranges_along
from app.services.projection import Projection, mean_lat

# Pieces left over after subtracting Overlap can be float slivers; ignore them.
MIN_ENCOUNTER_LENGTH_M = 1.0


def _subtract(
    ranges: list[tuple[float, float]], cut: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """Remove the `cut` ranges from `ranges` (all in metres along A)."""
    out = ranges
    for c_lo, c_hi in cut:
        next_out: list[tuple[float, float]] = []
        for lo, hi in out:
            if c_hi <= lo or c_lo >= hi:
                next_out.append((lo, hi))
                continue
            if c_lo > lo:
                next_out.append((lo, c_lo))
            if c_hi < hi:
                next_out.append((c_hi, hi))
        out = next_out
    return [(lo, hi) for lo, hi in out if hi - lo >= MIN_ENCOUNTER_LENGTH_M]


def compute_encounters(
    route_a_geometry: list[LonLat],
    route_b_geometry: list[LonLat],
    danger_distance_m: float,
    overlap_segments: list[OverlapSegment],
    merge_gap_m: float,
) -> list[Encounter]:
    if len(route_a_geometry) < 2 or len(route_b_geometry) < 2:
        return []

    proj = Projection(ref_lat=mean_lat(route_a_geometry, route_b_geometry))
    a_line = LineString(proj.to_xy(route_a_geometry))
    b_line = LineString(proj.to_xy(route_b_geometry))
    total_len = a_line.length
    if total_len == 0:
        return []

    close = as_linestrings(a_line.intersection(b_line.buffer(danger_distance_m)))
    stretches = merge_ranges(ranges_along(close, a_line), merge_gap_m)

    # Measure the overlap from its own geometry: its fractions are rounded to
    # 4 decimals, which is metres of error on a long route.
    overlap_lines = [
        LineString(proj.to_xy(s.geometry)) for s in overlap_segments if len(s.geometry) >= 2
    ]
    stretches = _subtract(stretches, ranges_along(overlap_lines, a_line))

    encounters: list[Encounter] = []
    for lo, hi in stretches:
        stretch = substring(a_line, lo, hi)
        closest, _ = nearest_points(stretch, b_line)
        gap = closest.distance(b_line)
        # Position within the stretch, so a route that loops back on itself
        # can't place the marker at the wrong visit.
        position = lo + stretch.project(closest)
        encounters.append(
            Encounter(
                location=proj.to_lonlat([(closest.x, closest.y)])[0],
                min_gap_m=round(gap, 1),
                position_fraction=round(position / total_len, 4),
                start_fraction=round(lo / total_len, 4),
                end_fraction=round(hi / total_len, 4),
                distance_m=round(hi - lo, 1),
                geometry=proj.to_lonlat(list(stretch.coords)),
            )
        )

    encounters.sort(key=lambda e: e.start_fraction)
    return encounters

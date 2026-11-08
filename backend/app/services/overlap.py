"""
Route overlap detection (spec §7-9, §31).

Approach:
  1. Project both routes from lon/lat into a local metric plane (see
     app/services/projection.py).
  2. Buffer route B by the fixed overlap tolerance (~25 m, "same road";
     deliberately not the user-set danger distance, ADR 0001) to get a
     "corridor" polygon.
  3. Intersect route A's line with that corridor. This answers "how much
     of *my* route runs inside a corridor around the other route" —
     which is what the user actually experiences as overlap.
  4. Drop slivers below min_meaningful_overlap_m (a single road crossing
     shouldn't count as an overlap — spec §31).
  5. Merge segments that are only a few metres apart (GPS noise /
     roundabouts) into one continuous overlap (spec §31).
  6. Express each surviving segment's position as a fraction along route
     A's total length, so the frontend can zoom to it (spec §9).

This module is pure Python/Shapely — no DB or network — so it's unit
tested directly (see tests/test_overlap.py).
"""
from shapely.geometry import LineString
from shapely.ops import linemerge, substring, unary_union

from app.schemas import LonLat, OverlapResult, OverlapSegment
from app.services.projection import Projection, mean_lat


def _as_linestrings(geom) -> list[LineString]:
    """Flatten a Shapely intersection result (which may be a LineString,
    MultiLineString, GeometryCollection, or empty) into a list of LineStrings."""
    if geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type == "MultiLineString":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        out = []
        for g in geom.geoms:
            out.extend(_as_linestrings(g))
        return out
    # Points / tiny polygons from near-tangent buffers: ignore.
    return []


def _merge_close_segments(segments: list[LineString], route_a: LineString, gap_m: float) -> list[LineString]:
    """Merge segments (as ranges along route_a) that are within gap_m of
    each other, so a shared road broken by a roundabout counts as one
    overlap instead of several (spec §31)."""
    if not segments:
        return []

    # Compute each segment's start/end distance-along-route_a so ranges
    # can be sorted and merged along a single 1D axis.
    ranges = []
    for seg in segments:
        p_start = seg.interpolate(0)
        p_end = seg.interpolate(1, normalized=True)
        d_start = route_a.project(p_start)
        d_end = route_a.project(p_end)
        lo, hi = min(d_start, d_end), max(d_start, d_end)
        ranges.append([lo, hi])

    ranges.sort(key=lambda r: r[0])
    merged: list[list[float]] = []
    for lo, hi in ranges:
        if merged and lo - merged[-1][1] <= gap_m:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])

    total_len = route_a.length
    out = []
    for lo, hi in merged:
        hi = min(hi, total_len)
        if hi - lo <= 0:
            continue
        out.append(substring(route_a, lo, hi))
    return out


def compute_overlap(
    route_a_geometry: list[LonLat],
    route_a_duration_min: float,
    route_b_geometry: list[LonLat],
    tolerance_m: float,
    min_meaningful_overlap_m: float,
    merge_gap_m: float,
) -> OverlapResult:
    if len(route_a_geometry) < 2 or len(route_b_geometry) < 2:
        return OverlapResult(distance_km=0, percentage=0, duration_min=0, segments=[])

    proj = Projection(ref_lat=mean_lat(route_a_geometry, route_b_geometry))
    a_line = LineString(proj.to_xy(route_a_geometry))
    b_line = LineString(proj.to_xy(route_b_geometry))

    if a_line.length == 0:
        return OverlapResult(distance_km=0, percentage=0, duration_min=0, segments=[])

    corridor = b_line.buffer(tolerance_m)
    raw_intersection = a_line.intersection(corridor)
    raw_segments = _as_linestrings(raw_intersection)

    # Drop slivers (incidental crossings, spec §31 "Intersections").
    substantial = [s for s in raw_segments if s.length >= min_meaningful_overlap_m]

    merged_segments = _merge_close_segments(substantial, a_line, merge_gap_m)

    total_overlap_m = sum(s.length for s in merged_segments)
    total_len_m = a_line.length
    percentage = round((total_overlap_m / total_len_m) * 100, 1) if total_len_m else 0.0
    overlap_duration_min = round((total_overlap_m / total_len_m) * route_a_duration_min, 1) if total_len_m else 0.0

    out_segments: list[OverlapSegment] = []
    for seg in merged_segments:
        p_start = seg.interpolate(0)
        p_end = seg.interpolate(1, normalized=True)
        d_start = a_line.project(p_start)
        d_end = a_line.project(p_end)
        seg_type = "shared_segment" if seg.length >= min_meaningful_overlap_m * 1.5 else "crossing"
        out_segments.append(
            OverlapSegment(
                type=seg_type,
                distance_m=round(seg.length, 1),
                geometry=proj.to_lonlat(list(seg.coords)),
                start_fraction=round(min(d_start, d_end) / total_len_m, 4) if total_len_m else 0,
                end_fraction=round(max(d_start, d_end) / total_len_m, 4) if total_len_m else 0,
            )
        )

    out_segments.sort(key=lambda s: s.start_fraction)

    return OverlapResult(
        distance_km=round(total_overlap_m / 1000, 2),
        percentage=percentage,
        duration_min=overlap_duration_min,
        segments=out_segments,
    )

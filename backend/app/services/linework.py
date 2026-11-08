"""
Small Shapely helpers shared by the overlap and encounter services.

Everything here works in the local metric plane (see projection.py), and
describes parts of route A as ranges of distance-along-A in metres.
"""
from shapely.geometry import LineString


def as_linestrings(geom) -> list[LineString]:
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
            out.extend(as_linestrings(g))
        return out
    # Points / tiny polygons from near-tangent buffers: ignore.
    return []


def ranges_along(segments: list[LineString], route: LineString) -> list[tuple[float, float]]:
    """Each segment as a (start, end) distance along `route`, in metres."""
    ranges = []
    for seg in segments:
        d_start = route.project(seg.interpolate(0))
        d_end = route.project(seg.interpolate(1, normalized=True))
        ranges.append((min(d_start, d_end), max(d_start, d_end)))
    return ranges


def merge_ranges(ranges: list[tuple[float, float]], gap_m: float) -> list[tuple[float, float]]:
    """Merge ranges that are within `gap_m` of each other (sorted by start)."""
    merged: list[list[float]] = []
    for lo, hi in sorted(ranges):
        if merged and lo - merged[-1][1] <= gap_m:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]

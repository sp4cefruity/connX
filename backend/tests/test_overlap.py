from app.schemas import LonLat
from app.services.overlap import compute_overlap


def _line(coords: list[tuple[float, float]]) -> list[LonLat]:
    return [LonLat(lon=lon, lat=lat) for lon, lat in coords]


def test_identical_routes_overlap_100_percent():
    route = _line([(85.80, 20.29), (85.81, 20.30), (85.82, 20.31)])
    result = compute_overlap(route, 10.0, route, tolerance_m=50, min_meaningful_overlap_m=20, merge_gap_m=25)
    assert result.percentage > 95  # essentially full overlap


def test_completely_different_routes_no_overlap():
    route_a = _line([(85.80, 20.29), (85.81, 20.30), (85.82, 20.31)])
    route_b = _line([(85.95, 20.50), (85.96, 20.51), (85.97, 20.52)])
    result = compute_overlap(route_a, 10.0, route_b, tolerance_m=50, min_meaningful_overlap_m=20, merge_gap_m=25)
    assert result.distance_km == 0
    assert result.percentage == 0
    assert result.segments == []


def test_single_crossing_is_not_counted_as_meaningful_overlap():
    # Two roughly perpendicular lines crossing at one point should not
    # register as a large "shared segment" overlap (spec §31).
    route_a = _line([(85.80, 20.29), (85.82, 20.29)])  # west->east
    route_b = _line([(85.81, 20.28), (85.81, 20.30)])  # south->north, crosses A near midpoint
    result = compute_overlap(route_a, 10.0, route_b, tolerance_m=15, min_meaningful_overlap_m=20, merge_gap_m=25)
    assert result.percentage < 15


def test_parallel_close_roads_flagged_at_high_sensitivity():
    route_a = _line([(85.800, 20.290), (85.820, 20.290)])
    # ~40m north of route_a throughout (roughly, at this latitude 0.0004 deg lat ~ 44m)
    route_b = _line([(85.800, 20.2904), (85.820, 20.2904)])

    low = compute_overlap(route_a, 10.0, route_b, tolerance_m=20, min_meaningful_overlap_m=20, merge_gap_m=25)
    high = compute_overlap(route_a, 10.0, route_b, tolerance_m=100, min_meaningful_overlap_m=20, merge_gap_m=25)

    assert high.percentage >= low.percentage
    assert high.percentage > 50


def test_multiple_overlap_segments_detected_separately():
    # A shares a corridor with B in two disjoint stretches, with a clear
    # gap (routed away and back) in between.
    route_a = _line(
        [
            (85.800, 20.290),
            (85.805, 20.290),  # shared start
            (85.808, 20.300),  # diverges north
            (85.812, 20.290),  # back to shared corridor
            (85.816, 20.290),  # shared end
        ]
    )
    route_b = _line([(85.800, 20.2901), (85.816, 20.2901)])

    result = compute_overlap(route_a, 10.0, route_b, tolerance_m=30, min_meaningful_overlap_m=20, merge_gap_m=25)
    assert len(result.segments) >= 2


def test_segments_are_ordered_along_route_a():
    route_a = _line(
        [
            (85.800, 20.290),
            (85.805, 20.290),
            (85.808, 20.300),
            (85.812, 20.290),
            (85.816, 20.290),
        ]
    )
    route_b = _line([(85.800, 20.2901), (85.816, 20.2901)])
    result = compute_overlap(route_a, 10.0, route_b, tolerance_m=30, min_meaningful_overlap_m=20, merge_gap_m=25)

    fractions = [s.start_fraction for s in result.segments]
    assert fractions == sorted(fractions)

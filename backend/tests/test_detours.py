"""Detour waypoint planning: given the trouble on a route (overlap with Route B,
close passes, Red spots it enters), pick via points on the far side of the route
so a detour can be routed around each one.

Route A runs due east along lat 20.290 from lon 85.800 to 85.820 (~2.1 km).
Route B is a parallel line 55 m north of it (lat 20.2905)."""
import math

import pytest
from shapely.geometry import LineString, Point

from app.schemas import Encounter, LonLat, OverlapResult, OverlapSegment, RouteResult
from app.services.detours import (
    MIN_OFFSET_M,
    AvoidCircle,
    Trouble,
    filter_detours,
    improves_on,
    plan_waypoints,
)
from app.services.projection import Projection

A_LAT = 20.290
B_NORTH_LAT = 20.2905
M_PER_DEG = 111_320.0

ROUTE = [LonLat(lon=85.800, lat=A_LAT), LonLat(lon=85.820, lat=A_LAT)]
B_NORTH = [LonLat(lon=85.800, lat=B_NORTH_LAT), LonLat(lon=85.820, lat=B_NORTH_LAT)]
B_SOUTH = [LonLat(lon=85.800, lat=A_LAT - 0.0005), LonLat(lon=85.820, lat=A_LAT - 0.0005)]
NO_OVERLAP = OverlapResult(distance_km=0, percentage=0, duration_min=0, segments=[])


def _metres(a: list[LonLat], b: LonLat) -> float:
    """Distance from point b to polyline a, in metres."""
    proj = Projection(ref_lat=A_LAT)
    return LineString(proj.to_xy(a)).distance(Point(proj.to_xy([b])[0]))


def _encounter(start: float, end: float, gap_m: float = 55.0) -> Encounter:
    mid = (start + end) / 2
    return Encounter(
        location=LonLat(lon=85.800 + 0.02 * mid, lat=A_LAT),
        min_gap_m=gap_m,
        position_fraction=mid,
        start_fraction=start,
        end_fraction=end,
        distance_m=100.0,
        geometry=[],
    )


def _overlap(start: float, end: float, distance_m: float = 400.0) -> OverlapResult:
    return OverlapResult(
        distance_km=distance_m / 1000,
        percentage=20,
        duration_min=1,
        segments=[
            OverlapSegment(
                type="shared_segment",
                distance_m=distance_m,
                geometry=[],
                start_fraction=start,
                end_fraction=end,
            )
        ],
    )


def _plan(**kw):
    args = dict(
        route=ROUTE,
        avoid_route=B_NORTH,
        avoid_circles=[],
        danger_distance_m=200.0,
        overlap=NO_OVERLAP,
        encounters=[],
    )
    args.update(kw)
    return plan_waypoints(**args)


def test_nothing_to_avoid_gives_no_waypoints():
    assert _plan() == []


def test_encounter_waypoint_sits_beside_the_stretch_on_the_side_away_from_b():
    (wp,) = _plan(encounters=[_encounter(0.4, 0.6)])
    assert wp.lat < A_LAT  # B is north, so the detour goes south
    assert wp.lon == pytest.approx(85.810, abs=0.0005)  # abreast of the stretch's middle
    assert _metres(ROUTE, wp) == pytest.approx(300.0, abs=5)  # 1.5 x the 200 m danger distance


def test_waypoint_goes_the_other_way_when_b_is_south():
    (wp,) = _plan(avoid_route=B_SOUTH, encounters=[_encounter(0.4, 0.6)])
    assert wp.lat > A_LAT


def test_offset_has_a_floor_so_a_narrow_danger_distance_still_leaves_the_road():
    (wp,) = _plan(danger_distance_m=50.0, encounters=[_encounter(0.4, 0.6)])
    assert _metres(ROUTE, wp) == pytest.approx(MIN_OFFSET_M, abs=5)


def test_overlap_waypoint_is_well_clear_of_the_shared_road():
    # B is the same road as A, so either side will do, but it must leave the road.
    (wp,) = _plan(avoid_route=ROUTE, overlap=_overlap(0.3, 0.7))
    assert _metres(B_NORTH, wp) > 250 or _metres(B_SOUTH, wp) > 250
    assert _metres(ROUTE, wp) == pytest.approx(300.0, abs=5)


def test_red_spot_waypoint_clears_the_circle():
    circle = AvoidCircle(lon=85.810, lat=B_NORTH_LAT, radius_m=100.0)
    (wp,) = _plan(avoid_route=None, avoid_circles=[circle])
    assert wp.lat < A_LAT
    centre = LonLat(lon=circle.lon, lat=circle.lat)
    assert _metres([centre, centre], wp) > 1.5 * circle.radius_m


def test_red_spots_are_planned_before_overlap_before_close_passes():
    circle = AvoidCircle(lon=85.805, lat=B_NORTH_LAT, radius_m=100.0)
    wps = _plan(
        avoid_circles=[circle],
        overlap=_overlap(0.45, 0.55),
        encounters=[_encounter(0.85, 0.95)],
        max_waypoints=2,
    )
    assert len(wps) == 2
    assert wps[0].lon < 85.808  # the Red spot at lon 85.805
    assert 85.808 < wps[1].lon < 85.812  # then the overlap, mid-route


def test_waypoints_are_capped():
    encounters = [_encounter(0.1, 0.15), _encounter(0.4, 0.45), _encounter(0.7, 0.75), _encounter(0.9, 0.95)]
    assert len(_plan(encounters=encounters, max_waypoints=3)) == 3


def test_closer_passes_are_planned_first():
    far = _encounter(0.1, 0.15, gap_m=150.0)
    near = _encounter(0.8, 0.85, gap_m=20.0)
    (wp,) = _plan(encounters=[far, near], max_waypoints=1)
    assert wp.lon > 85.815  # the near one, late in the route


def test_trouble_spots_close_together_share_one_waypoint():
    # Two stretches ~100 m apart along the route: one detour covers both.
    first, second = _encounter(0.40, 0.42), _encounter(0.45, 0.47)
    assert len(_plan(encounters=[first, second])) == 1


def _route(lat: float, duration_min: float = 4.0) -> RouteResult:
    return RouteResult(
        distance_km=2.1,
        duration_min=duration_min,
        geometry=[LonLat(lon=85.800, lat=lat), LonLat(lon=85.820, lat=lat)],
        mode="driving",
    )


def _filter(detours, existing):
    return filter_detours(
        detours,
        existing,
        tolerance_m=25.0,
        min_meaningful_overlap_m=30.0,
        merge_gap_m=30.0,
    )


def test_a_detour_on_the_same_road_as_an_existing_route_is_dropped():
    assert _filter([_route(A_LAT + 0.00001)], [_route(A_LAT)]) == []


def test_a_detour_on_a_different_road_is_kept():
    detour = _route(A_LAT - 0.003)
    assert _filter([detour], [_route(A_LAT)]) == [detour]


def test_two_detours_on_the_same_road_keep_only_the_first():
    first, second = _route(A_LAT - 0.003), _route(A_LAT - 0.00301)
    assert _filter([first, second], [_route(A_LAT)]) == [first]


def test_a_detour_much_slower_than_the_fastest_route_is_dropped():
    assert _filter([_route(A_LAT - 0.003, duration_min=8.5)], [_route(A_LAT, 4.0)]) == []


def test_a_detour_exactly_twice_as_slow_is_kept():
    detour = _route(A_LAT - 0.003, duration_min=8.0)
    assert _filter([detour], [_route(A_LAT, 4.0)]) == [detour]


def _t(shared_km=0.0, close_passes=0, red_spot_hits=0) -> Trouble:
    return Trouble(shared_km=shared_km, close_passes=close_passes, red_spot_hits=red_spot_hits)


def test_a_detour_sharing_the_same_km_with_b_is_not_an_improvement():
    # The live case: 14.35 km shared against 14.22 km before.
    assert not improves_on(_t(shared_km=14.35), baseline=_t(shared_km=14.22))


def test_a_detour_sharing_noticeably_less_road_is_an_improvement():
    assert improves_on(_t(shared_km=7.8), baseline=_t(shared_km=14.2))


def test_sharing_only_a_little_less_is_not_enough():
    assert not improves_on(_t(shared_km=12.0), baseline=_t(shared_km=14.2))  # 15% less


def test_fewer_close_passes_is_an_improvement():
    assert improves_on(_t(close_passes=1), baseline=_t(close_passes=3))


def test_leaving_a_red_spot_is_an_improvement():
    assert improves_on(_t(), baseline=_t(red_spot_hits=1))


def test_entering_more_red_spots_is_never_an_improvement():
    assert not improves_on(_t(shared_km=1.0, red_spot_hits=2), baseline=_t(shared_km=14.2, red_spot_hits=1))


def test_less_shared_road_does_not_excuse_more_shared_road_elsewhere():
    # Fewer close passes, but far more road shared with B.
    assert not improves_on(_t(shared_km=20.0, close_passes=0), baseline=_t(shared_km=14.2, close_passes=2))


def test_offset_distance_is_metric_not_degrees():
    (wp,) = _plan(encounters=[_encounter(0.4, 0.6)])
    dlat_m = abs(wp.lat - A_LAT) * M_PER_DEG
    assert math.isclose(dlat_m, 300.0, abs_tol=5)

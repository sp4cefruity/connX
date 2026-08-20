from app.schemas import LonLat, OverlapResult, RedSpot, RedSpotHit, RouteResult
from app.services.scoring import ScoringInputs, score_route


def _route(distance_km: float, duration_min: float) -> RouteResult:
    return RouteResult(
        distance_km=distance_km,
        duration_min=duration_min,
        geometry=[LonLat(lon=0, lat=0), LonLat(lon=1, lat=1)],
        mode="driving",
    )


def _overlap(pct: float) -> OverlapResult:
    return OverlapResult(distance_km=0, percentage=pct, duration_min=0, segments=[])


def test_slower_zero_overlap_route_beats_faster_high_overlap_route():
    # Mirrors spec §34: Route A 24min/2km overlap vs Route B 27min/0km overlap -> B should score better.
    route_a = _route(distance_km=9.2, duration_min=24)
    route_b = _route(distance_km=10.1, duration_min=27)

    score_a = score_route(
        ScoringInputs(
            route=route_a,
            overlap=_overlap(20.0),
            red_spot_hits=[],
            avoid_overlap=True,
            avoid_red_spots=True,
            fastest_duration_min=24,
            shortest_distance_km=9.2,
        )
    )
    score_b = score_route(
        ScoringInputs(
            route=route_b,
            overlap=_overlap(0.0),
            red_spot_hits=[],
            avoid_overlap=True,
            avoid_red_spots=True,
            fastest_duration_min=24,
            shortest_distance_km=9.2,
        )
    )
    assert score_b.total < score_a.total


def test_dramatically_longer_zero_overlap_route_loses_to_reasonable_one():
    # Route B (27min, 0 overlap) should still beat Route C (61min, 0 overlap) -> spec §34.
    route_b = _route(distance_km=10.1, duration_min=27)
    route_c = _route(distance_km=14.0, duration_min=61)

    score_b = score_route(
        ScoringInputs(
            route=route_b, overlap=_overlap(0.0), red_spot_hits=[],
            avoid_overlap=True, avoid_red_spots=True,
            fastest_duration_min=24, shortest_distance_km=9.2,
        )
    )
    score_c = score_route(
        ScoringInputs(
            route=route_c, overlap=_overlap(0.0), red_spot_hits=[],
            avoid_overlap=True, avoid_red_spots=True,
            fastest_duration_min=24, shortest_distance_km=9.2,
        )
    )
    assert score_b.total < score_c.total


def test_red_zone_outranks_overlap_penalty():
    # spec §32: a route avoiding a red spot should usually beat one that
    # enters it, even with some overlap and a bit more time.
    home = RedSpot(id="00000000-0000-0000-0000-000000000000", name="Home", latitude=0, longitude=0, radius_m=100, created_at="2024-01-01T00:00:00")

    route_hits_home = _route(distance_km=9.0, duration_min=25)
    route_avoids_home = _route(distance_km=9.8, duration_min=29)

    score_hits = score_route(
        ScoringInputs(
            route=route_hits_home,
            overlap=_overlap(0.0),
            red_spot_hits=[RedSpotHit(red_spot=home, intersects=True, min_distance_m=10)],
            avoid_overlap=True, avoid_red_spots=True,
            fastest_duration_min=25, shortest_distance_km=9.0,
        )
    )
    score_avoids = score_route(
        ScoringInputs(
            route=route_avoids_home,
            overlap=_overlap(5.0),
            red_spot_hits=[RedSpotHit(red_spot=home, intersects=False, min_distance_m=800)],
            avoid_overlap=True, avoid_red_spots=True,
            fastest_duration_min=25, shortest_distance_km=9.0,
        )
    )
    assert score_avoids.total < score_hits.total


def test_avoid_overlap_toggle_off_removes_overlap_penalty():
    route = _route(distance_km=9.2, duration_min=24)
    score = score_route(
        ScoringInputs(
            route=route, overlap=_overlap(80.0), red_spot_hits=[],
            avoid_overlap=False, avoid_red_spots=True,
            fastest_duration_min=24, shortest_distance_km=9.2,
        )
    )
    assert score.overlap_penalty == 0

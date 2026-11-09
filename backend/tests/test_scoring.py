from app.schemas import Encounter, LonLat, OverlapResult, RedSpot, RedSpotHit, RouteResult
from app.services.scoring import W_ENCOUNTER, ScoringInputs, explain, score_route


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


# ---------- encounter term (ticket 07) ----------


def _encounter(gap_m: float) -> Encounter:
    return Encounter(
        location=LonLat(lon=0.5, lat=0.5),
        min_gap_m=gap_m,
        position_fraction=0.5,
        start_fraction=0.4,
        end_fraction=0.6,
        distance_m=120,
        geometry=[LonLat(lon=0.4, lat=0.4), LonLat(lon=0.6, lat=0.6)],
    )


def _score(encounters, danger_distance_m=200.0, avoid_overlap=True, duration_min=24.0):
    return score_route(
        ScoringInputs(
            route=_route(distance_km=9.2, duration_min=duration_min),
            overlap=_overlap(0.0),
            red_spot_hits=[],
            avoid_overlap=avoid_overlap,
            avoid_red_spots=True,
            fastest_duration_min=24,
            shortest_distance_km=9.2,
            encounters=encounters,
            danger_distance_m=danger_distance_m,
        )
    )


def test_no_encounters_means_no_encounter_penalty():
    assert _score([]).encounter_penalty == 0


def test_encounter_penalty_is_part_of_the_total():
    score = _score([_encounter(60)])
    assert score.encounter_penalty > 0
    assert score.total == score.encounter_penalty  # everything else is zero here


def test_fewer_close_passes_rank_better():
    one = _score([_encounter(100)])
    two = _score([_encounter(100), _encounter(100)])
    assert one.total < two.total


def test_more_distant_close_pass_ranks_better():
    near = _score([_encounter(20)])
    far = _score([_encounter(180)])
    assert far.total < near.total


def test_closeness_is_measured_against_the_danger_distance():
    # The same 150 m gap grazes the edge of a 1 km band but sits deep in a
    # 160 m one.
    wide = _score([_encounter(150)], danger_distance_m=1000)
    narrow = _score([_encounter(150)], danger_distance_m=160)
    assert wide.encounter_penalty > narrow.encounter_penalty


def test_each_close_pass_costs_between_one_and_two_weights():
    edge = _score([_encounter(200)], danger_distance_m=200)
    touching = _score([_encounter(0)], danger_distance_m=200)
    assert edge.encounter_penalty == W_ENCOUNTER
    assert touching.encounter_penalty == 2 * W_ENCOUNTER


def test_avoid_overlap_toggle_off_removes_encounter_penalty():
    assert _score([_encounter(10)], avoid_overlap=False).encounter_penalty == 0


def test_slightly_slower_route_without_close_passes_beats_faster_one_with_a_close_pass():
    faster_close = _score([_encounter(30)], duration_min=24)
    slower_clear = _score([], duration_min=27)
    assert slower_clear.total < faster_close.total


def test_ordering_between_candidates_follows_close_passes():
    candidates = {
        "two_near": _score([_encounter(30), _encounter(40)]),
        "one_near": _score([_encounter(30)]),
        "one_far": _score([_encounter(190)]),
        "clear": _score([]),
    }
    ranked = sorted(candidates, key=lambda k: candidates[k].total)
    assert ranked == ["clear", "one_far", "one_near", "two_near"]


# ---------- explanations ----------


def _explain(encounters, danger_distance_m=200.0):
    route = _route(distance_km=9.2, duration_min=24)
    return explain(route, _overlap(0.0), [], route, encounters, danger_distance_m)


def test_explanation_counts_close_passes_and_names_the_nearest_gap():
    lines = _explain([_encounter(140.2), _encounter(60.4)])
    assert "2 close passes, nearest 60 m" in lines


def test_explanation_for_a_single_close_pass():
    assert "1 close pass, 60 m away" in _explain([_encounter(60)])


def test_explanation_with_no_close_passes_mentions_the_danger_distance():
    assert "No close passes within 200 m" in _explain([])
    assert "No close passes within 1 km" in _explain([], danger_distance_m=1000)


def test_explanation_omits_close_passes_without_a_route_to_avoid():
    lines = _explain(None)
    assert not any("close pass" in line.lower() for line in lines)

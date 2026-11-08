"""Encounters: stretches of Route A within the danger distance of Route B,
excluding Overlap. Pure Shapely, no DB or network (like test_overlap.py)."""
import pytest

from app.config import get_settings
from app.schemas import LonLat
from app.services.encounters import compute_encounters
from app.services.overlap import compute_overlap

SETTINGS = get_settings()
M_PER_DEG_LAT = 111_320.0
DANGER_M = 200.0


def _line(coords: list[tuple[float, float]]) -> list[LonLat]:
    return [LonLat(lon=lon, lat=lat) for lon, lat in coords]


def _north(metres: float) -> float:
    """Degrees of latitude for a northward offset in metres."""
    return metres / M_PER_DEG_LAT


def _encounters(a, b, danger=DANGER_M, overlap_segments=None, merge_gap_m=SETTINGS.overlap_merge_gap_m):
    return compute_encounters(a, b, danger, overlap_segments or [], merge_gap_m)


ROUTE_B = _line([(85.800, 20.290), (85.840, 20.290)])


def test_parallel_route_just_inside_danger_distance_is_one_encounter():
    a = _line([(85.800, 20.290 + _north(199)), (85.820, 20.290 + _north(199))])
    result = _encounters(a, ROUTE_B)
    assert len(result) == 1
    assert result[0].min_gap_m == pytest.approx(199, abs=1.0)


def test_parallel_route_just_outside_danger_distance_has_no_encounter():
    a = _line([(85.800, 20.290 + _north(201)), (85.820, 20.290 + _north(201))])
    assert _encounters(a, ROUTE_B) == []


def test_closest_point_is_where_the_gap_is_smallest():
    # A dips toward B and back out; the nearest vertex is the middle one.
    a = _line([(85.800, 20.2920), (85.810, 20.2905), (85.820, 20.2920)])
    result = _encounters(a, ROUTE_B)
    assert len(result) == 1
    enc = result[0]
    assert enc.min_gap_m == pytest.approx(0.0005 * M_PER_DEG_LAT, abs=1.0)  # ~55.7 m
    assert enc.location.lon == pytest.approx(85.810, abs=1e-4)
    assert enc.location.lat == pytest.approx(20.2905, abs=1e-4)
    assert enc.position_fraction == pytest.approx(0.5, abs=0.02)


def _out_and_back():
    """Close to B, a long detour far away, then close to B again."""
    return _line(
        [
            (85.800, 20.2910),
            (85.810, 20.2910),
            (85.810, 20.3000),
            (85.820, 20.3000),
            (85.820, 20.2910),
            (85.830, 20.2910),
        ]
    )


def test_separate_close_stretches_are_separate_encounters_ordered_along_a():
    result = _encounters(_out_and_back(), ROUTE_B)
    assert len(result) == 2
    first, second = result
    assert first.position_fraction < second.position_fraction
    assert first.end_fraction < second.start_fraction


def test_stretches_closer_than_the_merge_gap_become_one_encounter():
    assert len(_encounters(_out_and_back(), ROUTE_B, merge_gap_m=25)) == 2
    assert len(_encounters(_out_and_back(), ROUTE_B, merge_gap_m=5000)) == 1


def test_encounter_reports_its_stretch_length_and_geometry():
    a = _line([(85.800, 20.290 + _north(100)), (85.820, 20.290 + _north(100))])
    enc = _encounters(a, ROUTE_B)[0]
    assert enc.distance_m == pytest.approx(0.020 * M_PER_DEG_LAT * 0.9396, rel=0.02)  # ~2.09 km at 20.29N
    assert len(enc.geometry) >= 2
    assert enc.start_fraction == pytest.approx(0, abs=0.01)
    assert enc.end_fraction == pytest.approx(1, abs=0.01)


def test_fully_overlapping_routes_have_no_encounters():
    overlap = compute_overlap(
        ROUTE_B, 10, ROUTE_B,
        tolerance_m=SETTINGS.overlap_tolerance_m,
        min_meaningful_overlap_m=SETTINGS.min_meaningful_overlap_m,
        merge_gap_m=SETTINGS.overlap_merge_gap_m,
    )
    assert overlap.segments  # sanity: overlap really was found
    assert _encounters(ROUTE_B, ROUTE_B, overlap_segments=overlap.segments) == []


def test_overlap_is_never_double_counted_as_an_encounter():
    # A shares B's road for the first half, then veers off but stays within 200 m.
    a = _line(
        [
            (85.800, 20.2901),
            (85.820, 20.2901),
            (85.820, 20.2914),
            (85.840, 20.2914),
        ]
    )
    overlap = compute_overlap(
        a, 10, ROUTE_B,
        tolerance_m=SETTINGS.overlap_tolerance_m,
        min_meaningful_overlap_m=SETTINGS.min_meaningful_overlap_m,
        merge_gap_m=SETTINGS.overlap_merge_gap_m,
    )
    assert len(overlap.segments) == 1
    seg = overlap.segments[0]

    result = _encounters(a, ROUTE_B, overlap_segments=overlap.segments)
    assert len(result) == 1
    enc = result[0]
    assert enc.start_fraction >= seg.end_fraction - 1e-3
    assert enc.min_gap_m >= SETTINGS.overlap_tolerance_m - 1.0

    # Without the overlap input the same stretch is reported as one long encounter.
    unfiltered = _encounters(a, ROUTE_B)
    assert unfiltered[0].start_fraction < seg.end_fraction


def test_overlap_exclusion_uses_segment_geometry_not_rounded_fractions():
    """Fractions are rounded to 4 decimals (metres of error on a long route), so
    the exclusion must follow the segment's own geometry."""
    a = _line([(85.800, 20.2901), (85.820, 20.2901), (85.820, 20.2914), (85.840, 20.2914)])
    overlap = compute_overlap(
        a, 10, ROUTE_B,
        tolerance_m=SETTINGS.overlap_tolerance_m,
        min_meaningful_overlap_m=SETTINGS.min_meaningful_overlap_m,
        merge_gap_m=SETTINGS.overlap_merge_gap_m,
    )
    exact = _encounters(a, ROUTE_B, overlap_segments=overlap.segments)

    skewed = [s.model_copy(update={"start_fraction": 0.0, "end_fraction": 0.2}) for s in overlap.segments]
    assert _encounters(a, ROUTE_B, overlap_segments=skewed) == exact


def test_empty_or_degenerate_geometry_has_no_encounters():
    assert _encounters([], ROUTE_B) == []
    assert _encounters(ROUTE_B, []) == []
    assert _encounters(_line([(85.8, 20.29)]), ROUTE_B) == []

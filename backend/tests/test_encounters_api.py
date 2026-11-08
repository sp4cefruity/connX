"""Compare and recommend report Encounters. Route B runs ~55 m north of A (the
shared test fixture), so it is a near-miss for danger distances above 55 m."""
import pytest

from tests.test_danger_distance_api import _compare_body, _recommend_body, client  # noqa: F401


def test_compare_reports_encounter_when_within_danger_distance(client):
    body = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=100)).json()
    assert len(body["encounters"]) == 1
    enc = body["encounters"][0]
    assert enc["min_gap_m"] == pytest.approx(55.7, abs=1.0)
    assert 0 <= enc["position_fraction"] <= 1
    assert enc["location"]["lat"] == pytest.approx(20.290, abs=1e-3)
    assert len(enc["geometry"]) >= 2


def test_compare_reports_no_encounter_outside_danger_distance(client):
    body = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=50)).json()
    assert body["encounters"] == []


def test_danger_distance_changes_encounters_but_not_overlap(client):
    near = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=50)).json()
    far = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=500)).json()
    assert near["overlap"] == far["overlap"]
    assert len(near["encounters"]) == 0 and len(far["encounters"]) == 1


def test_recommend_attaches_encounters_to_each_scored_route(client):
    body = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=100)).json()
    assert all(len(r["encounters"]) == 1 for r in body["routes"])
    body = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=50)).json()
    assert all(r["encounters"] == [] for r in body["routes"])


def test_recommend_without_comparison_route_has_no_encounters(client):
    body = _recommend_body(danger_distance_m=500)
    body["comparison_start"] = body["comparison_end"] = None
    res = client.post("/api/routes/recommend", json=body).json()
    assert all(r["encounters"] == [] for r in res["routes"])

"""/recommend ranks candidates with the encounter term, using the request's
danger distance (ticket 07).

Route B runs along lat 20.2905. Candidate "near" runs ~55 m south of it and is
half a minute faster; candidate "far" runs ~610 m south of it."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_or_create_user
from app.database import get_db
from app.routers import routes as routes_router
from app.routing import get_routing_provider
from app.schemas import LonLat, RouteResult
from tests.test_danger_distance_api import _recommend_body

B_LAT = 20.2905
NEAR_LAT = 20.290
FAR_LAT = 20.285


def _line(lat: float, duration_min: float) -> RouteResult:
    return RouteResult(
        distance_km=1.9,
        duration_min=duration_min,
        geometry=[LonLat(lon=85.800, lat=lat), LonLat(lon=85.820, lat=lat)],
        mode="driving",
    )


class _TwoCandidates:
    async def get_route(self, start, end, mode):
        return _line(B_LAT, 4.0)  # only used for Route B here

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [_line(NEAR_LAT, 4.0), _line(FAR_LAT, 4.5)]


class _FakeUser:
    id = "user-1"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_router.router)
    app.dependency_overrides[get_routing_provider] = lambda: _TwoCandidates()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_or_create_user] = lambda: _FakeUser()
    return TestClient(app)


def _recommend(client, danger_distance_m):
    res = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=danger_distance_m))
    assert res.status_code == 200
    return res.json()


def _recommended_lat(body):
    return body["routes"][body["recommended_index"]]["route"]["geometry"][0]["lat"]


def test_close_pass_pushes_the_faster_candidate_down(client):
    body = _recommend(client, 100)
    assert _recommended_lat(body) == FAR_LAT
    near = next(r for r in body["routes"] if r["route"]["geometry"][0]["lat"] == NEAR_LAT)
    assert near["score"]["encounter_penalty"] > 0


def test_without_close_passes_the_faster_candidate_wins(client):
    # 50 m is narrower than either gap: no encounters, so time decides.
    body = _recommend(client, 50)
    assert _recommended_lat(body) == NEAR_LAT
    assert all(r["score"]["encounter_penalty"] == 0 for r in body["routes"])


def test_routes_are_sorted_by_total_score(client):
    body = _recommend(client, 1000)
    totals = [r["score"]["total"] for r in body["routes"]]
    assert totals == sorted(totals)
    # Both pass within 1 km; the more distant pass still ranks better.
    assert _recommended_lat(body) == FAR_LAT


def test_explanations_mention_close_passes(client):
    body = _recommend(client, 100)
    by_lat = {r["route"]["geometry"][0]["lat"]: r["explanation"] for r in body["routes"]}
    assert "1 close pass, 56 m away" in by_lat[NEAR_LAT]
    assert "No close passes within 100 m" in by_lat[FAR_LAT]


def test_avoid_overlap_off_ignores_close_passes(client):
    res = client.post(
        "/api/routes/recommend", json=_recommend_body(danger_distance_m=100, avoid_overlap=False)
    )
    body = res.json()
    assert _recommended_lat(body) == NEAR_LAT
    assert all(r["score"]["encounter_penalty"] == 0 for r in body["routes"])


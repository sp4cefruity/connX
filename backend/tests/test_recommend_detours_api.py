"""/recommend builds its own detour candidates when the provider's alternatives
are too few and the best route still has trouble on it.

The provider here returns a single route along lat 20.290, which is exactly
Route Bs road (full overlap). A detour via a point beside the road is a line at
the via point's latitude, so the tests can see where the detour went."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point, shape

from app.auth import get_or_create_user
from app.database import get_db
from app.routers import routes as routes_router
from app.routing import get_routing_provider
from app.routing.base import RoutingProviderError
from app.schemas import LonLat, RouteResult
from tests.test_danger_distance_api import _recommend_body

ROAD_LAT = 20.290
FAR_LAT = 20.300  # ~1.1 km from the road


def _line(lat: float, duration_min: float) -> RouteResult:
    return RouteResult(
        distance_km=2.1,
        duration_min=duration_min,
        geometry=[LonLat(lon=85.800, lat=lat), LonLat(lon=85.820, lat=lat)],
        mode="driving",
    )


class _Provider:
    """One direct route on the road; detours land at the via point's latitude."""

    def __init__(self, via_duration_min=5.0, via_lat=None, via_error=None, via_geometry=None, avoid_lat=None):
        self.via_calls: list[LonLat] = []
        self.avoid_calls: list[dict] = []
        self._avoid_lat = avoid_lat  # None: this provider cannot route around an area
        self._via_duration = via_duration_min
        self._via_lat = via_lat
        self._via_error = via_error
        self._via_geometry = via_geometry

    async def get_route(self, start, end, mode):
        return _line(start.lat, 4.0)  # Route B, when asked: a line at its start latitude

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [_line(ROAD_LAT, 4.0)]

    async def get_route_avoiding(self, start, end, mode, avoid):
        self.avoid_calls.append(avoid)
        if self._avoid_lat is None:
            raise RoutingProviderError("this provider cannot route around an area")
        return _line(self._avoid_lat, 5.0)

    async def get_route_via(self, start, via, end, mode):
        self.via_calls.append(via)
        if self._via_error:
            raise self._via_error
        if self._via_geometry:
            return RouteResult(
                distance_km=2.5, duration_min=self._via_duration, geometry=self._via_geometry, mode="driving"
            )
        lat = via.lat if self._via_lat is None else self._via_lat
        return _line(lat, self._via_duration)


class _FakeUser:
    id = "user-1"


def _client(provider) -> TestClient:
    app = FastAPI()
    app.include_router(routes_router.router)
    app.dependency_overrides[get_routing_provider] = lambda: provider
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_or_create_user] = lambda: _FakeUser()
    return TestClient(app)


def _body(**extra):
    """A's trip along the road, B also on the road: full overlap."""
    body = _recommend_body(**extra)
    body["comparison_start"] = {"lon": 85.800, "lat": ROAD_LAT}
    body["comparison_end"] = {"lon": 85.820, "lat": ROAD_LAT}
    return body


def _post(client, body):
    res = client.post("/api/routes/recommend", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _recommended(body):
    return body["routes"][body["recommended_index"]]


def _lat(scored):
    return scored["route"]["geometry"][0]["lat"]


NO_BETTER_ROUTE = "No better route found nearby"


def test_detour_around_the_shared_road_is_recommended():
    provider = _Provider()
    body = _post(_client(provider), _body())

    assert len(body["routes"]) == 2
    best = _recommended(body)
    assert _lat(best) != ROAD_LAT
    assert best["overlap"]["percentage"] == 0
    assert best["tier"] == "recommended"
    assert provider.via_calls, "the detour should have been routed via a waypoint"
    assert abs(provider.via_calls[0].lat - ROAD_LAT) * 111_320 >= 250


def test_the_original_route_is_still_offered_with_its_overlap():
    body = _post(_client(_Provider()), _body())
    original = next(r for r in body["routes"] if _lat(r) == ROAD_LAT)
    assert original["overlap"]["percentage"] == 100
    assert original["tier"] != "recommended"


def test_a_clean_route_triggers_no_detour_calls():
    provider = _Provider()
    far_b = _body()
    far_b["comparison_start"] = {"lon": 85.800, "lat": FAR_LAT}
    far_b["comparison_end"] = {"lon": 85.820, "lat": FAR_LAT}
    body = _post(_client(provider), far_b)
    assert provider.via_calls == []
    assert len(body["routes"]) == 1
    assert NO_BETTER_ROUTE not in " ".join(_recommended(body)["explanation"])


def test_no_detour_calls_when_the_provider_already_gave_enough_routes():
    provider = _Provider()
    _post(_client(provider), _body(alternatives_count=1))
    assert provider.via_calls == []


def test_no_detour_calls_when_overlap_avoidance_is_off():
    provider = _Provider()
    _post(_client(provider), _body(avoid_overlap=False))
    assert provider.via_calls == []


def test_a_failed_detour_leaves_the_original_route_and_says_so():
    provider = _Provider(via_error=RoutingProviderError("boom"))
    body = _post(_client(provider), _body())
    assert len(body["routes"]) == 1
    assert NO_BETTER_ROUTE in _recommended(body)["explanation"]


def test_a_detour_that_snaps_back_to_the_same_road_is_dropped():
    provider = _Provider(via_lat=ROAD_LAT)
    body = _post(_client(provider), _body())
    assert len(body["routes"]) == 1
    assert NO_BETTER_ROUTE in _recommended(body)["explanation"]


def test_a_detour_that_rejoins_the_shared_road_and_shares_as_much_is_dropped():
    # Leaves the road for a 300 m bump in the middle, then rejoins it: longer,
    # so its overlap percentage is lower, but it shares nearly the same km.
    bump = [
        LonLat(lon=85.800, lat=ROAD_LAT),
        LonLat(lon=85.8085, lat=ROAD_LAT),
        LonLat(lon=85.8100, lat=ROAD_LAT - 0.0027),
        LonLat(lon=85.8115, lat=ROAD_LAT),
        LonLat(lon=85.820, lat=ROAD_LAT),
    ]
    provider = _Provider(via_geometry=bump)
    body = _post(_client(provider), _body())
    assert provider.via_calls, "the detour should have been tried"
    assert len(body["routes"]) == 1
    assert NO_BETTER_ROUTE in _recommended(body)["explanation"]


def test_a_far_slower_detour_is_dropped():
    provider = _Provider(via_duration_min=9.0)  # more than 2 x the 4 min road
    body = _post(_client(provider), _body())
    assert len(body["routes"]) == 1


CLEAR_LAT = ROAD_LAT - 0.003  # ~330 m south of the shared road


def test_a_route_around_the_shared_road_is_tried_first_and_needs_no_via_points():
    provider = _Provider(avoid_lat=CLEAR_LAT)
    body = _post(_client(provider), _body())

    assert len(provider.avoid_calls) == 1
    assert provider.via_calls == []
    zone = shape(provider.avoid_calls[0])
    assert zone.contains(Point(85.810, ROAD_LAT))  # keeps clear of Route B's road
    assert not zone.contains(Point(85.810, ROAD_LAT + 0.001))  # but only its road
    best = _recommended(body)
    assert _lat(best) == CLEAR_LAT
    assert best["overlap"]["percentage"] == 0
    assert len(body["routes"]) == 2


def test_when_the_provider_cannot_avoid_areas_via_point_detours_are_used():
    provider = _Provider()  # avoid raises
    body = _post(_client(provider), _body())
    assert len(provider.avoid_calls) == 1
    assert provider.via_calls
    assert _lat(_recommended(body)) != ROAD_LAT


def test_an_avoid_route_that_still_shares_the_road_is_not_offered_and_via_points_take_over():
    provider = _Provider(avoid_lat=ROAD_LAT)  # "avoids" it, but lands right back on the road
    body = _post(_client(provider), _body())
    assert provider.via_calls
    assert all(r["overlap"]["percentage"] < 100 for r in body["routes"] if r["tier"] == "recommended")


def test_no_avoid_call_when_the_route_has_nothing_to_avoid():
    provider = _Provider(avoid_lat=CLEAR_LAT)
    far_b = _body()
    far_b["comparison_start"] = {"lon": 85.800, "lat": FAR_LAT}
    far_b["comparison_end"] = {"lon": 85.820, "lat": FAR_LAT}
    _post(_client(provider), far_b)
    assert provider.avoid_calls == []


def test_no_avoid_call_when_the_provider_already_gave_enough_routes():
    provider = _Provider(avoid_lat=CLEAR_LAT)
    _post(_client(provider), _body(alternatives_count=1))
    assert provider.avoid_calls == []


def test_nothing_works_leaves_the_original_with_the_explanation():
    provider = _Provider(via_error=RoutingProviderError("boom"))  # avoid raises too
    body = _post(_client(provider), _body())
    assert len(body["routes"]) == 1
    assert NO_BETTER_ROUTE in _recommended(body)["explanation"]


def test_the_avoid_zone_includes_red_spots_the_route_enters(monkeypatch):
    spot = _red_spot(85.810, ROAD_LAT, radius_m=150.0)
    monkeypatch.setattr(routes_router, "get_active_red_spots", lambda db, user_id: [spot])
    provider = _Provider(avoid_lat=CLEAR_LAT)
    body = _recommend_body(avoid_red_spots=True)
    body["comparison_start"] = body["comparison_end"] = None

    result = _post(_client(provider), body)

    zone = shape(provider.avoid_calls[0])
    assert zone.contains(Point(85.810, ROAD_LAT))
    assert zone.contains(Point(85.810, ROAD_LAT + 120 / 111_320))
    assert not any(h["intersects"] for h in _recommended(result)["red_spot_hits"])


def _red_spot(lon: float, lat: float, radius_m: float = 100.0):
    return SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 1, 1),
        name="Priya's house",
        latitude=lat,
        longitude=lon,
        radius_m=radius_m,
        type=None,
        temporary=False,
        expires_at=None,
    )


def test_a_red_spot_on_the_route_gets_a_detour_around_it(monkeypatch):
    spot = _red_spot(85.810, ROAD_LAT)
    monkeypatch.setattr(routes_router, "get_active_red_spots", lambda db, user_id: [spot])
    provider = _Provider()
    body = _recommend_body(avoid_red_spots=True)
    body["comparison_start"] = body["comparison_end"] = None

    result = _post(_client(provider), body)

    best = _recommended(result)
    assert provider.via_calls
    assert _lat(best) != ROAD_LAT
    assert not any(h["intersects"] for h in best["red_spot_hits"])


@pytest.mark.parametrize("count,expected_calls", [(2, 1), (3, 2)])
def test_detour_calls_never_exceed_the_routes_still_wanted(monkeypatch, count, expected_calls):
    # Two separate trouble spots: shared road mid-route, a Red spot near the end.
    spot = _red_spot(85.8185, ROAD_LAT)
    monkeypatch.setattr(routes_router, "get_active_red_spots", lambda db, user_id: [spot])
    provider = _Provider()
    _post(_client(provider), _body(alternatives_count=count, avoid_red_spots=True))
    assert len(provider.via_calls) == expected_calls

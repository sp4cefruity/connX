"""get_route_via: route start -> via -> end on every provider and wrapper."""
import asyncio
import json

import httpx
import pytest

from app.routing.base import RoutingProviderError
from app.routing.mock import MockRouting
from app.routing.ors import ORSRouting
from app.routing.osrm import OSRMRouting
from app.routing.wrappers import CachedRouting, FallbackRouting
from app.schemas import LonLat, RouteResult

START = LonLat(lon=85.8245, lat=20.2961)
VIA = LonLat(lon=85.8300, lat=20.2900)
VIA_2 = LonLat(lon=85.8310, lat=20.2800)
END = LonLat(lon=85.8400, lat=20.3100)


def run(coro):
    return asyncio.run(coro)


def _route(km: float = 1.0) -> RouteResult:
    return RouteResult(distance_km=km, duration_min=5, geometry=[START, VIA, END], mode="driving")


# ---------- OSRM ----------


def test_osrm_routes_through_the_via_point_without_alternatives():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 4200,
                        "duration": 600,
                        "geometry": {"coordinates": [[85.8245, 20.2961], [85.83, 20.29], [85.84, 20.31]]},
                    }
                ],
            },
        )

    osrm = OSRMRouting({"walking": "http://osrm.test"}, transport=httpx.MockTransport(handler))
    route = run(osrm.get_route_via(START, VIA, END, "walking"))

    assert seen[0].url.path.endswith("/85.8245,20.2961;85.83,20.29;85.84,20.31")
    assert seen[0].url.params["alternatives"] == "false"
    assert route.distance_km == 4.2
    assert route.mode == "walking"


def test_osrm_via_failure_is_a_provider_error():
    osrm = OSRMRouting(
        {"driving": "http://osrm.test"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"code": "NoRoute", "routes": []})),
    )
    with pytest.raises(RoutingProviderError):
        run(osrm.get_route_via(START, VIA, END, "driving"))


# ---------- ORS ----------


def test_ors_sends_start_via_end_and_no_alternatives_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "properties": {"summary": {"distance": 4200, "duration": 600}},
                        "geometry": {"coordinates": [[85.8245, 20.2961], [85.83, 20.29], [85.84, 20.31]]},
                    }
                ]
            },
        )

    ors = ORSRouting("key-123", transport=httpx.MockTransport(handler))
    route = run(ors.get_route_via(START, VIA, END, "cycling"))

    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v2/directions/cycling-regular/geojson"
    assert body["coordinates"] == [[85.8245, 20.2961], [85.83, 20.29], [85.84, 20.31]]
    assert "alternative_routes" not in body
    assert route.duration_min == 10.0


# ---------- mock ----------


def test_mock_route_via_passes_through_the_via_point():
    route = run(MockRouting().get_route_via(START, VIA, END, "driving"))
    assert route.geometry[0] == START
    assert route.geometry[-1] == END
    assert VIA in route.geometry
    assert route.distance_km > run(MockRouting().get_route(START, END, "driving")).distance_km


# ---------- cache ----------


class _CountingInner:
    def __init__(self):
        self.via_calls = 0

    async def get_route(self, start, end, mode):
        return _route()

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [_route()]

    async def get_route_via(self, start, via, end, mode):
        self.via_calls += 1
        return _route(km=float(self.via_calls))


def test_cache_serves_the_same_via_route_once():
    inner = _CountingInner()
    cached = CachedRouting(inner)
    first = run(cached.get_route_via(START, VIA, END, "driving"))
    second = run(cached.get_route_via(START, VIA, END, "driving"))
    assert inner.via_calls == 1
    assert first == second


def test_cache_keeps_different_via_points_apart():
    inner = _CountingInner()
    cached = CachedRouting(inner)
    run(cached.get_route_via(START, VIA, END, "driving"))
    run(cached.get_route_via(START, VIA_2, END, "driving"))
    assert inner.via_calls == 2


def test_cache_does_not_confuse_a_via_route_with_the_direct_route():
    inner = _CountingInner()
    cached = CachedRouting(inner)
    direct = run(cached.get_route(START, END, "driving"))
    via = run(cached.get_route_via(START, VIA, END, "driving"))
    assert inner.via_calls == 1
    assert via.distance_km == 1.0 and direct.distance_km == 1.0


def test_cache_does_not_store_failures():
    class _Flaky(_CountingInner):
        async def get_route_via(self, start, via, end, mode):
            self.via_calls += 1
            if self.via_calls == 1:
                raise RoutingProviderError("boom")
            return _route()

    inner = _Flaky()
    cached = CachedRouting(inner)
    with pytest.raises(RoutingProviderError):
        run(cached.get_route_via(START, VIA, END, "driving"))
    run(cached.get_route_via(START, VIA, END, "driving"))
    assert inner.via_calls == 2


# ---------- fallback ----------


def test_fallback_uses_the_second_provider_for_via_routes():
    class _Down(_CountingInner):
        async def get_route_via(self, start, via, end, mode):
            raise RoutingProviderError("down")

    backup = _CountingInner()
    route = run(FallbackRouting(_Down(), backup).get_route_via(START, VIA, END, "driving"))
    assert backup.via_calls == 1
    assert route.distance_km == 1.0

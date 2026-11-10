"""get_route_avoiding: route start -> end keeping out of a GeoJSON area.

Only ORS can do it. OSRM and the mock refuse, so the caller falls back to via
points. Quota refusals trip the circuit breaker; an ordinary "no route that
avoids this" does not (it says nothing about the provider's health)."""
import asyncio
import json

import httpx
import pytest

from app.routing.base import RoutingProviderError, RoutingQuotaError
from app.routing.mock import MockRouting
from app.routing.ors import ORSRouting
from app.routing.osrm import OSRMRouting
from app.routing.wrappers import CachedRouting, FallbackRouting
from app.schemas import LonLat, RouteResult

START = LonLat(lon=85.8245, lat=20.2961)
END = LonLat(lon=85.8400, lat=20.3100)
ZONE = {"type": "Polygon", "coordinates": [[[85.83, 20.29], [85.84, 20.29], [85.84, 20.30], [85.83, 20.29]]]}
OTHER_ZONE = {"type": "Polygon", "coordinates": [[[85.80, 20.20], [85.81, 20.20], [85.81, 20.21], [85.80, 20.20]]]}


def run(coro):
    return asyncio.run(coro)


def _route(km: float = 1.0) -> RouteResult:
    return RouteResult(distance_km=km, duration_min=5, geometry=[START, END], mode="driving")


def _feature() -> dict:
    return {
        "properties": {"summary": {"distance": 4200, "duration": 600}},
        "geometry": {"coordinates": [[85.8245, 20.2961], [85.84, 20.31]]},
    }


# ---------- ORS ----------


def test_ors_sends_the_zone_as_avoid_polygons_and_asks_for_one_route():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"features": [_feature()]})

    ors = ORSRouting("key-123", transport=httpx.MockTransport(handler))
    route = run(ors.get_route_avoiding(START, END, "driving", ZONE))

    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v2/directions/driving-car/geojson"
    assert body["coordinates"] == [[85.8245, 20.2961], [85.84, 20.31]]
    assert body["options"] == {"avoid_polygons": ZONE}
    assert "alternative_routes" not in body
    assert route.distance_km == 4.2


def test_ors_no_route_around_the_zone_is_a_plain_provider_error():
    ors = ORSRouting(
        "key-123",
        transport=httpx.MockTransport(lambda r: httpx.Response(404, json={"error": {"code": 2009}})),
    )
    with pytest.raises(RoutingProviderError) as err:
        run(ors.get_route_avoiding(START, END, "driving", ZONE))
    assert not isinstance(err.value, RoutingQuotaError)


def test_ors_quota_refusal_is_a_quota_error():
    ors = ORSRouting("key-123", transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(RoutingQuotaError):
        run(ors.get_route_avoiding(START, END, "driving", ZONE))


# ---------- providers that cannot ----------


def test_osrm_cannot_avoid_areas():
    osrm = OSRMRouting({"driving": "http://osrm.test"})
    with pytest.raises(RoutingProviderError):
        run(osrm.get_route_avoiding(START, END, "driving", ZONE))


def test_mock_cannot_avoid_areas():
    with pytest.raises(RoutingProviderError):
        run(MockRouting().get_route_avoiding(START, END, "driving", ZONE))


# ---------- cache ----------


class _Inner:
    def __init__(self):
        self.avoid_calls = 0

    async def get_route(self, start, end, mode):
        return _route()

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [_route()]

    async def get_route_avoiding(self, start, end, mode, avoid):
        self.avoid_calls += 1
        return _route(km=float(self.avoid_calls))


def test_cache_serves_the_same_avoid_route_once():
    inner = _Inner()
    cached = CachedRouting(inner)
    first = run(cached.get_route_avoiding(START, END, "driving", ZONE))
    second = run(cached.get_route_avoiding(START, END, "driving", dict(ZONE)))
    assert inner.avoid_calls == 1
    assert first == second


def test_cache_keeps_different_zones_apart():
    inner = _Inner()
    cached = CachedRouting(inner)
    run(cached.get_route_avoiding(START, END, "driving", ZONE))
    run(cached.get_route_avoiding(START, END, "driving", OTHER_ZONE))
    assert inner.avoid_calls == 2


def test_cache_does_not_confuse_an_avoid_route_with_the_direct_route():
    inner = _Inner()
    cached = CachedRouting(inner)
    run(cached.get_route(START, END, "driving"))
    run(cached.get_route_avoiding(START, END, "driving", ZONE))
    assert inner.avoid_calls == 1


# ---------- fallback ----------


class _Quota(_Inner):
    async def get_route_avoiding(self, start, end, mode, avoid):
        self.avoid_calls += 1
        raise RoutingQuotaError("429")


class _NoRoute(_Inner):
    async def get_route_avoiding(self, start, end, mode, avoid):
        self.avoid_calls += 1
        raise RoutingProviderError("no route around that")


class _Counting(_Inner):
    def __init__(self):
        super().__init__()
        self.route_calls = 0

    async def get_route(self, start, end, mode):
        self.route_calls += 1
        return _route()


def test_fallback_lets_a_no_route_error_through_without_tripping_the_breaker():
    primary, backup = _NoRoute(), _Counting()
    fb = FallbackRouting(primary, backup, failure_threshold=1)
    for _ in range(3):
        with pytest.raises(RoutingProviderError):
            run(fb.get_route_avoiding(START, END, "driving", ZONE))
    # Even with a threshold of 1, those failures did not disable the primary.
    run(fb.get_route(START, END, "driving"))
    assert backup.route_calls == 0


def test_fallback_quota_refusal_disables_the_primary_for_ordinary_routes_too():
    primary, backup = _Quota(), _Counting()
    fb = FallbackRouting(primary, backup)
    with pytest.raises(RoutingQuotaError):
        run(fb.get_route_avoiding(START, END, "driving", ZONE))
    run(fb.get_route(START, END, "driving"))
    assert backup.route_calls == 1  # primary is skipped now


def test_fallback_does_not_ask_the_primary_again_while_it_is_disabled():
    primary, backup = _Quota(), _Counting()
    fb = FallbackRouting(primary, backup)
    with pytest.raises(RoutingQuotaError):
        run(fb.get_route_avoiding(START, END, "driving", ZONE))
    with pytest.raises(RoutingProviderError):
        run(fb.get_route_avoiding(START, END, "driving", ZONE))
    assert primary.avoid_calls == 1

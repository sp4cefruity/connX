"""ORS provider, routing fallback, route cache, TTL cache. No live network."""
import asyncio
import json

import httpx
import pytest

from app.cache import TTLCache
from app.config import Settings
from app.routing import get_routing_provider
from app.routing.base import RoutingProviderError, RoutingQuotaError
from app.routing.ors import ORSRouting
from app.routing.osrm import OSRMRouting
from app.routing.wrappers import CachedRouting, FallbackRouting
from app.schemas import LonLat, RouteResult

START = LonLat(lon=85.8245, lat=20.2961)
END = LonLat(lon=85.8400, lat=20.3100)


def run(coro):
    return asyncio.run(coro)


def _feature(distance_m: float) -> dict:
    return {
        "properties": {"summary": {"distance": distance_m, "duration": 600}},
        "geometry": {"coordinates": [[85.8245, 20.2961], [85.84, 20.31]]},
    }


def _ors(handler) -> ORSRouting:
    return ORSRouting("key-123", transport=httpx.MockTransport(handler))


def _route(km: float = 1.0) -> RouteResult:
    return RouteResult(
        distance_km=km, duration_min=5, geometry=[START, END], mode="driving"
    )


# ---------- TTLCache ----------


def test_ttl_cache_expires_entries():
    now = [0.0]
    cache: TTLCache[int] = TTLCache(ttl_s=10, max_entries=5, clock=lambda: now[0])
    cache.set("a", 1)
    now[0] = 9.9
    assert cache.get("a") == 1
    now[0] = 10.0
    assert cache.get("a") is None
    assert len(cache) == 0


def test_ttl_cache_evicts_least_recently_used():
    cache: TTLCache[int] = TTLCache(ttl_s=100, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # a is now the most recently used
    cache.set("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3


# ---------- ORS ----------


def test_ors_sends_key_profile_and_parses_alternatives():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"features": [_feature(2000), _feature(2600)]})

    routes = run(_ors(handler).get_alternative_routes(START, END, "walking", count=3))
    req = seen[0]
    assert req.url.path == "/v2/directions/foot-walking/geojson"
    assert req.headers["authorization"] == "key-123"
    body = json.loads(req.content)
    assert body["coordinates"] == [[85.8245, 20.2961], [85.84, 20.31]]
    assert body["alternative_routes"]["target_count"] == 3
    assert [r.distance_km for r in routes] == [2.0, 2.6]
    assert all(r.mode == "walking" for r in routes)


def test_ors_single_route_does_not_request_alternatives():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"features": [_feature(1000)]})

    run(_ors(handler).get_route(START, END, "cycling"))
    assert "alternative_routes" not in bodies[0]


def test_ors_retries_without_alternatives_when_request_is_refused():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "alternative_routes" in body:
            return httpx.Response(
                400, json={"error": {"code": 2004, "message": "too long for alternatives"}}
            )
        return httpx.Response(200, json={"features": [_feature(150000)]})

    routes = run(_ors(handler).get_alternative_routes(START, END, "driving", count=3))
    assert len(bodies) == 2 and len(routes) == 1


def test_ors_other_400_does_not_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"code": 2010, "message": "point not routable"}})

    with pytest.raises(RoutingProviderError):
        run(_ors(handler).get_alternative_routes(START, END, "driving", count=3))
    assert len(calls) == 1


def test_ors_400_with_unparseable_body_does_not_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, text="nope")

    with pytest.raises(RoutingProviderError):
        run(_ors(handler).get_alternative_routes(START, END, "driving", count=3))
    assert len(calls) == 1


@pytest.mark.parametrize("status", [401, 403, 429])
def test_ors_quota_statuses_raise_quota_error(status):
    with pytest.raises(RoutingQuotaError):
        run(_ors(lambda r: httpx.Response(status)).get_route(START, END, "driving"))


@pytest.mark.parametrize("status", [403, 429, 500])
def test_ors_http_errors_are_routing_errors(status):
    with pytest.raises(RoutingProviderError):
        run(_ors(lambda r: httpx.Response(status)).get_route(START, END, "driving"))


def test_ors_garbled_body_is_a_routing_error():
    with pytest.raises(RoutingProviderError):
        run(_ors(lambda r: httpx.Response(200, json={"features": [{}]})).get_route(START, END, "driving"))


# ---------- fallback + cache wrappers ----------


class FakeRouting:
    def __init__(self, fail: bool = False, km: float = 1.0):
        self.fail, self.km, self.calls = fail, km, 0

    async def get_route(self, start, end, mode):
        self.calls += 1
        if self.fail:
            raise RoutingProviderError("down")
        return _route(self.km)

    async def get_alternative_routes(self, start, end, mode, count=3):
        self.calls += 1
        if self.fail:
            raise RoutingProviderError("down")
        return [_route(self.km)] * count


def test_fallback_uses_primary_when_healthy():
    primary, fallback = FakeRouting(km=1), FakeRouting(km=9)
    assert run(FallbackRouting(primary, fallback).get_route(START, END, "driving")).distance_km == 1
    assert fallback.calls == 0


def test_fallback_used_when_primary_fails():
    primary, fallback = FakeRouting(fail=True), FakeRouting(km=9)
    routing = FallbackRouting(primary, fallback)
    assert run(routing.get_route(START, END, "driving")).distance_km == 9
    assert len(run(routing.get_alternative_routes(START, END, "driving", 2))) == 2


def test_both_failing_raises():
    routing = FallbackRouting(FakeRouting(fail=True), FakeRouting(fail=True))
    with pytest.raises(RoutingProviderError):
        run(routing.get_route(START, END, "driving"))


def test_cache_serves_repeat_requests_without_calling_provider():
    inner = FakeRouting()
    routing = CachedRouting(inner)
    run(routing.get_route(START, END, "driving"))
    run(routing.get_route(START, END, "driving"))
    assert inner.calls == 1


def test_cache_key_covers_mode_count_and_endpoints():
    inner = FakeRouting()
    routing = CachedRouting(inner)
    run(routing.get_route(START, END, "driving"))
    run(routing.get_route(START, END, "walking"))
    run(routing.get_alternative_routes(START, END, "driving", 3))
    run(routing.get_alternative_routes(START, END, "driving", 2))
    run(routing.get_route(END, START, "driving"))
    assert inner.calls == 5


def test_cache_treats_metre_level_jitter_as_the_same_point():
    inner = FakeRouting()
    routing = CachedRouting(inner)
    run(routing.get_route(START, END, "driving"))
    run(routing.get_route(LonLat(lon=START.lon + 0.000001, lat=START.lat), END, "driving"))
    assert inner.calls == 1


def test_failures_are_not_cached():
    inner = FakeRouting(fail=True)
    routing = CachedRouting(inner)
    for _ in range(2):
        with pytest.raises(RoutingProviderError):
            run(routing.get_route(START, END, "driving"))
    assert inner.calls == 2


def test_fallback_skips_primary_during_cooldown_after_quota_error():
    now = [0.0]

    class Quota(FakeRouting):
        async def get_route(self, start, end, mode):
            self.calls += 1
            raise RoutingQuotaError("429")

    primary, fallback = Quota(), FakeRouting(km=9)
    routing = FallbackRouting(primary, fallback, cooldown_s=60, clock=lambda: now[0])
    for _ in range(3):
        assert run(routing.get_route(START, END, "driving")).distance_km == 9
    assert primary.calls == 1
    now[0] = 61
    run(routing.get_route(START, END, "driving"))
    assert primary.calls == 2


def test_fallback_opens_breaker_after_repeated_failures_and_success_resets():
    now = [0.0]
    primary, fallback = FakeRouting(fail=True), FakeRouting(km=9)
    routing = FallbackRouting(primary, fallback, cooldown_s=60, failure_threshold=3, clock=lambda: now[0])
    for _ in range(5):
        run(routing.get_route(START, END, "driving"))
    assert primary.calls == 3

    now[0] = 100
    primary.fail = False
    run(routing.get_route(START, END, "driving"))  # success resets the count
    primary.fail = True
    for _ in range(2):
        run(routing.get_route(START, END, "driving"))
    assert primary.calls == 6  # breaker not open yet (2 < 3)


def test_cache_returns_copies():
    routing = CachedRouting(FakeRouting())
    first = run(routing.get_route(START, END, "driving"))
    first.geometry.append(START)
    first.distance_km = 999
    second = run(routing.get_route(START, END, "driving"))
    assert second.distance_km == 1.0 and len(second.geometry) == 2

    alts = run(routing.get_alternative_routes(START, END, "driving", 2))
    alts.pop()
    alts[0].distance_km = 999
    again = run(routing.get_alternative_routes(START, END, "driving", 2))
    assert len(again) == 2 and again[0].distance_km == 1.0


def test_single_route_shared_between_get_route_and_alternatives_count_1():
    inner = FakeRouting()
    routing = CachedRouting(inner)
    run(routing.get_route(START, END, "driving"))
    alts = run(routing.get_alternative_routes(START, END, "driving", 1))
    assert len(alts) == 1 and inner.calls == 1


def test_concurrent_identical_requests_share_one_upstream_call():
    class Slow(FakeRouting):
        async def get_route(self, start, end, mode):
            self.calls += 1
            await asyncio.sleep(0.01)
            return _route()

    inner = Slow()
    routing = CachedRouting(inner)

    async def go():
        return await asyncio.gather(
            routing.get_route(START, END, "driving"),
            routing.get_alternative_routes(START, END, "driving", 1),
            routing.get_route(START, END, "driving"),
        )

    results = run(go())
    assert inner.calls == 1 and len(results) == 3


def test_failed_in_flight_request_is_not_cached_and_can_retry():
    inner = FakeRouting(fail=True)
    routing = CachedRouting(inner)

    async def go():
        return await asyncio.gather(
            routing.get_route(START, END, "driving"),
            routing.get_route(START, END, "driving"),
            return_exceptions=True,
        )

    assert all(isinstance(r, RoutingProviderError) for r in run(go()))
    inner.fail = False
    assert run(routing.get_route(START, END, "driving")).distance_km == 1.0


# ---------- factory ----------


def _provider_for(monkeypatch, **overrides):
    import app.routing as routing_pkg

    settings = Settings(_env_file=None, geocoding_provider="mock", **overrides)
    monkeypatch.setattr(routing_pkg, "get_settings", lambda: settings)
    get_routing_provider.cache_clear()
    try:
        return get_routing_provider()
    finally:
        get_routing_provider.cache_clear()


def test_factory_ors_with_key_is_cached_ors_over_osrm(monkeypatch):
    provider = _provider_for(monkeypatch, routing_provider="ors", ors_api_key="k")
    # Each provider is cached on its own; the fallback chain itself is not,
    # so degraded OSRM answers can't outlive an ORS recovery.
    chain = provider._routing
    assert isinstance(chain, FallbackRouting)
    assert isinstance(chain._primary, CachedRouting)
    assert isinstance(chain._primary._inner, ORSRouting)
    assert isinstance(chain._fallback, CachedRouting)
    assert isinstance(chain._fallback._inner, OSRMRouting)


def test_factory_ors_without_key_degrades_to_osrm(monkeypatch):
    provider = _provider_for(monkeypatch, routing_provider="ors", ors_api_key="")
    assert isinstance(provider._routing, CachedRouting)
    assert isinstance(provider._routing._inner, OSRMRouting)

"""Valhalla provider and its OSRM fallback. No live network."""
import asyncio
import json

import httpx
import pytest

pytest.skip("Valhalla is parked (ADR 0007)", allow_module_level=True)

from app.config import Settings
from app.routing import get_routing_provider
from app.routing.base import RoutingProviderError
from app.routing.osrm import OSRMRouting
from app.routing.valhalla import ValhallaRouting, decode_polyline6
from app.routing.wrappers import CachedRouting, FallbackRouting
from app.schemas import LonLat

START = LonLat(lon=85.8245, lat=20.2961)
END = LonLat(lon=85.8400, lat=20.3100)
VIA = LonLat(lon=85.83, lat=20.30)


def run(coro):
    return asyncio.run(coro)


def encode6(points) -> str:
    """Encode (lon, lat) pairs as a polyline6 string (the inverse of the decoder)."""
    out, plat, plon = [], 0, 0
    for lon, lat in points:
        ilat, ilon = round(lat * 1e6), round(lon * 1e6)
        for d in (ilat - plat, ilon - plon):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def _trip(length_km=2.5, seconds=300, legs=None) -> dict:
    legs = legs or [[(85.8245, 20.2961), (85.84, 20.31)]]
    return {
        "legs": [{"shape": encode6(leg)} for leg in legs],
        "summary": {"length": length_km, "time": seconds},
    }


def _valhalla(handler) -> ValhallaRouting:
    return ValhallaRouting("http://valhalla:8002/", transport=httpx.MockTransport(handler))


def test_polyline_roundtrip():
    pts = [(85.824512, 20.296123), (85.84, 20.31), (85.8, 20.2)]
    got = decode_polyline6(encode6(pts))
    assert [(round(p.lon, 6), round(p.lat, 6)) for p in got] == pts


def test_get_route_posts_costing_per_mode_and_parses():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={"trip": _trip()})

    v = _valhalla(handler)
    for mode, costing in [("driving", "auto"), ("walking", "pedestrian"), ("cycling", "bicycle")]:
        route = run(v.get_route(START, END, mode))
        assert route.mode == mode
        assert seen[-1][1]["costing"] == costing
    assert seen[0][0] == "http://valhalla:8002/route"
    assert seen[0][1]["locations"][0] == {"lat": START.lat, "lon": START.lon, "type": "break"}
    assert route.distance_km == 2.5
    assert route.duration_min == 5.0
    assert route.geometry[0].lon == pytest.approx(85.8245)
    assert route.geometry[-1].lat == pytest.approx(20.31)


def test_alternatives_requested_and_parsed():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={"trip": _trip(2.0), "alternates": [{"trip": _trip(3.0)}, {"trip": _trip(4.0)}]},
        )

    routes = run(_valhalla(handler).get_alternative_routes(START, END, "driving", count=3))
    assert bodies[0]["alternates"] == 2
    assert [r.distance_km for r in routes] == [2.0, 3.0, 4.0]


def test_via_uses_through_location_and_joins_legs():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        legs = [[(85.8245, 20.2961), (85.83, 20.30)], [(85.83, 20.30), (85.84, 20.31)]]
        return httpx.Response(200, json={"trip": _trip(legs=legs)})

    route = run(_valhalla(handler).get_route_via(START, VIA, END, "driving"))
    assert [loc["type"] for loc in bodies[0]["locations"]] == ["break", "through", "break"]
    assert "alternates" not in bodies[0]
    assert len(route.geometry) == 3  # the shared joint point is not repeated


def test_avoiding_sends_exclude_polygons():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={"trip": _trip()})

    ring = [[85.83, 20.29], [85.84, 20.29], [85.84, 20.30], [85.83, 20.29]]
    area = {"type": "MultiPolygon", "coordinates": [[ring]]}
    run(_valhalla(handler).get_route_avoiding(START, END, "driving", area))
    assert bodies[0]["exclude_polygons"] == [ring]

    with pytest.raises(RoutingProviderError):
        run(_valhalla(handler).get_route_avoiding(START, END, "driving", {"type": "Point", "coordinates": [0, 0]}))


def test_errors_become_routing_provider_error():
    def no_edges(req):
        return httpx.Response(400, json={"error_code": 171, "error": "No suitable edges near location"})

    with pytest.raises(RoutingProviderError, match="171"):
        run(_valhalla(no_edges).get_route(START, END, "driving"))

    def boom(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(RoutingProviderError):
        run(_valhalla(boom).get_route(START, END, "driving"))

    def junk(req):
        return httpx.Response(200, json={"nope": 1})

    with pytest.raises(RoutingProviderError):
        run(_valhalla(junk).get_route(START, END, "driving"))


def _osrm_ok(req):
    return httpx.Response(
        200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 9000,
                    "duration": 600,
                    "geometry": {"coordinates": [[85.8245, 20.2961], [85.84, 20.31]]},
                }
            ],
        },
    )


def _osrm() -> OSRMRouting:
    urls = {m: "http://osrm" for m in ("driving", "walking", "cycling")}
    return OSRMRouting(urls, transport=httpx.MockTransport(_osrm_ok))


def test_falls_back_to_osrm_when_valhalla_out_of_coverage(caplog):
    def no_edges(req):
        return httpx.Response(400, json={"error_code": 171, "error": "No suitable edges near location"})

    chain = FallbackRouting(_valhalla(no_edges), _osrm())
    with caplog.at_level("WARNING"):
        route = run(chain.get_route(START, END, "driving"))
    assert route.distance_km == 9.0
    assert "falling back" in caplog.text or "using fallback" in caplog.text


def test_falls_back_to_osrm_when_valhalla_is_down():
    def boom(req):
        raise httpx.ConnectError("refused")

    chain = FallbackRouting(_valhalla(boom), _osrm())
    assert run(chain.get_route(START, END, "walking")).distance_km == 9.0


def test_factory_valhalla_is_cached_valhalla_over_osrm(monkeypatch):
    import app.routing as routing_pkg

    settings = Settings(
        _env_file=None,
        geocoding_provider="mock",
        routing_provider="valhalla",
        valhalla_base_url="http://valhalla:8002",
    )
    monkeypatch.setattr(routing_pkg, "get_settings", lambda: settings)
    get_routing_provider.cache_clear()
    try:
        provider = get_routing_provider()
    finally:
        get_routing_provider.cache_clear()
    chain = provider._routing
    assert isinstance(chain, FallbackRouting)
    assert isinstance(chain._primary, CachedRouting)
    assert isinstance(chain._primary._inner, ValhallaRouting)
    assert chain._primary._inner.base_url == "http://valhalla:8002"
    assert isinstance(chain._fallback._inner, OSRMRouting)


def test_rejected_requests_do_not_trip_the_breaker():
    # Points outside the tiles (HTTP 400) fall back per request but are not an outage.
    calls = []

    def no_edges(req):
        calls.append(1)
        return httpx.Response(400, json={"error_code": 171, "error": "No suitable edges near location"})

    chain = FallbackRouting(_valhalla(no_edges), _osrm(), failure_threshold=3)
    for _ in range(5):
        assert run(chain.get_route(START, END, "driving")).distance_km == 9.0
    assert len(calls) == 5  # Valhalla was still asked every time


def test_unreachable_valhalla_trips_the_breaker():
    calls = []

    def boom(req):
        calls.append(1)
        raise httpx.ConnectError("refused")

    chain = FallbackRouting(_valhalla(boom), _osrm(), failure_threshold=3)
    for _ in range(5):
        run(chain.get_route(START, END, "driving"))
    assert len(calls) == 3  # skipped once the breaker opened


def test_avoiding_counts_an_unreachable_valhalla_but_not_a_rejection():
    area = {"type": "Polygon", "coordinates": [[[85.8, 20.2], [85.9, 20.2], [85.9, 20.3], [85.8, 20.2]]]}
    rejected, down = [], []

    def too_big(req):
        rejected.append(1)
        return httpx.Response(400, json={"error_code": 154, "error": "Path distance exceeds the max"})

    def boom(req):
        down.append(1)
        raise httpx.ConnectError("refused")

    chain = FallbackRouting(_valhalla(too_big), _osrm(), failure_threshold=2)
    for _ in range(4):
        with pytest.raises(RoutingProviderError):
            run(chain.get_route_avoiding(START, END, "driving", area))
    assert len(rejected) == 4

    chain = FallbackRouting(_valhalla(boom), _osrm(), failure_threshold=2)
    for _ in range(4):
        with pytest.raises(RoutingProviderError):
            run(chain.get_route_avoiding(START, END, "driving", area))
    assert len(down) == 2

"""Per-mode OSRM server selection (ADR 0002). No live network: httpx MockTransport."""
import asyncio

import httpx
import pytest

from app.config import Settings
from app.routing import get_routing_provider
from app.routing.base import RoutingProviderError
from app.routing.mock import MockRouting
from app.routing.osrm import OSRMRouting
from app.schemas import LonLat

URLS = {
    "driving": "https://car.test/routed-car/",  # trailing slash must be tolerated
    "walking": "https://foot.test/routed-foot",
    "cycling": "https://bike.test/routed-bike",
}
START = LonLat(lon=-0.1276, lat=51.5074)
END = LonLat(lon=-0.0877, lat=51.5155)


def _payload(distance: float) -> dict:
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": distance,
                "duration": 600,
                "geometry": {"coordinates": [[-0.1276, 51.5074], [-0.0877, 51.5155]]},
            }
        ],
    }


def _provider(handler) -> OSRMRouting:
    return OSRMRouting(URLS, transport=httpx.MockTransport(handler))


def test_each_mode_hits_its_own_server():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_payload(1000))

    routing = _provider(handler)
    for mode in ("driving", "walking", "cycling"):
        asyncio.run(routing.get_route(START, END, mode))

    assert [(r.url.host, r.url.path.split("/route/")[0]) for r in seen] == [
        ("car.test", "/routed-car"),
        ("foot.test", "/routed-foot"),
        ("bike.test", "/routed-bike"),
    ]
    # Servers ignore the URL profile; we always send the universally accepted one.
    assert all("/route/v1/driving/" in r.url.path for r in seen)


def test_result_is_tagged_with_requested_mode_and_parsed():
    routing = _provider(lambda request: httpx.Response(200, json=_payload(2500)))
    result = asyncio.run(routing.get_route(START, END, "walking"))
    assert result.mode == "walking"
    assert result.distance_km == 2.5
    assert result.duration_min == 10.0


def test_alternatives_use_the_mode_server():
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        assert request.url.params["alternatives"] == "true"
        return httpx.Response(200, json=_payload(1000))

    asyncio.run(_provider(handler).get_alternative_routes(START, END, "cycling", count=3))
    assert hosts == ["bike.test"]


def test_missing_mode_url_is_a_routing_error():
    routing = OSRMRouting({"driving": URLS["driving"]}, transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(RoutingProviderError):
        asyncio.run(routing.get_route(START, END, "walking"))


def test_http_failure_surfaces_as_routing_error():
    routing = _provider(lambda request: httpx.Response(503))
    with pytest.raises(RoutingProviderError):
        asyncio.run(routing.get_route(START, END, "driving"))


def test_osrm_no_route_surfaces_as_routing_error():
    routing = _provider(lambda request: httpx.Response(200, json={"code": "NoRoute", "routes": []}))
    with pytest.raises(RoutingProviderError):
        asyncio.run(routing.get_route(START, END, "cycling"))


def test_default_settings_point_at_osm_car_foot_bike_servers():
    s = Settings(_env_file=None)
    assert s.osrm_driving_base_url.endswith("/routed-car")
    assert s.osrm_walking_base_url.endswith("/routed-foot")
    assert s.osrm_cycling_base_url.endswith("/routed-bike")


def test_factory_wires_per_mode_urls_from_settings(monkeypatch):
    import app.routing as routing_pkg

    settings = Settings(
        _env_file=None,
        routing_provider="osrm",
        geocoding_provider="mock",
        osrm_driving_base_url="https://a.test",
        osrm_walking_base_url="https://b.test",
        osrm_cycling_base_url="https://c.test",
    )
    monkeypatch.setattr(routing_pkg, "get_settings", lambda: settings)
    get_routing_provider.cache_clear()
    try:
        provider = get_routing_provider()
        assert provider._routing.base_urls == {
            "driving": "https://a.test",
            "walking": "https://b.test",
            "cycling": "https://c.test",
        }
    finally:
        get_routing_provider.cache_clear()


def test_mock_provider_still_works_for_every_mode():
    routing = MockRouting()
    for mode in ("driving", "walking", "cycling"):
        result = asyncio.run(routing.get_route(START, END, mode))
        assert result.mode == mode
        assert result.geometry

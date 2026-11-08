"""Geocoding: Photon -> Nominatim fallback, viewport-bias cache key, 503 signal.
No live network — providers are in-process fakes / httpx mock transports."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import geocode as geocode_router
from app.routing import CompositeProvider, get_routing_provider
from app.routing.base import RoutingProviderError
from app.routing.mock import MockGeocoding, MockRouting
from app.routing.photon import FallbackGeocoding, PhotonGeocoding
from app.schemas import GeocodeResult


class FakeGeocoder:
    def __init__(self, fail: bool = False, label: str = "fake"):
        self.fail = fail
        self.label = label
        self.calls: list[tuple] = []
        self.reverse_calls = 0

    async def geocode(self, query, limit=5, lat=None, lon=None):
        self.calls.append((query, limit, lat, lon))
        if self.fail:
            raise RoutingProviderError(f"{self.label} down")
        return [GeocodeResult(label=f"{self.label}:{query}", lon=lon or 0.0, lat=lat or 0.0)]

    async def reverse_geocode(self, lon, lat):
        self.reverse_calls += 1
        return GeocodeResult(label=self.label, lon=lon, lat=lat)


def run(coro):
    return asyncio.run(coro)


# ---------- fallback wrapper ----------


def test_fallback_uses_primary_when_healthy():
    primary, fallback = FakeGeocoder(label="photon"), FakeGeocoder(label="nominatim")
    res = run(FallbackGeocoding(primary, fallback).geocode("cafe", 5, lat=20.3, lon=85.8))
    assert res[0].label == "photon:cafe"
    assert primary.calls == [("cafe", 5, 20.3, 85.8)]
    assert fallback.calls == []


def test_fallback_to_nominatim_on_primary_error():
    primary, fallback = FakeGeocoder(fail=True, label="photon"), FakeGeocoder(label="nominatim")
    res = run(FallbackGeocoding(primary, fallback).geocode("cafe"))
    assert res[0].label == "nominatim:cafe"
    assert len(primary.calls) == 1 and len(fallback.calls) == 1


def test_both_fail_raises_provider_error():
    geo = FallbackGeocoding(FakeGeocoder(fail=True), FakeGeocoder(fail=True))
    with pytest.raises(RoutingProviderError):
        run(geo.geocode("cafe"))


def test_reverse_geocode_always_uses_fallback_nominatim():
    primary, fallback = FakeGeocoder(label="photon"), FakeGeocoder(label="nominatim")
    res = run(FallbackGeocoding(primary, fallback).reverse_geocode(85.8, 20.3))
    assert res.label == "nominatim"
    assert fallback.reverse_calls == 1 and primary.reverse_calls == 0


# ---------- Photon provider (mock HTTP transport) ----------

_PHOTON_BODY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Biju Patnaik International Airport",
                "street": "Harihar Singh Place",
                "city": "Bhubaneswar Municipal Corporation",
                "state": "Odisha",
                "country": "India",
            },
            "geometry": {"type": "Point", "coordinates": [85.8134847, 20.2522954]},
        },
        {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [1, 2]}},
    ],
}


def _photon_with_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.routing.photon.httpx.AsyncClient", factory)
    return PhotonGeocoding("https://photon.example/")


def test_photon_parses_features_and_sends_bias(monkeypatch):
    seen = {}

    def handler(request: httpx.Request):
        seen.update(request.url.params)
        seen["path"] = request.url.path
        return httpx.Response(200, json=_PHOTON_BODY)

    photon = _photon_with_transport(monkeypatch, handler)
    res = run(photon.geocode("airport", limit=3, lat=20.3, lon=85.8))

    assert seen["path"] == "/api/"
    assert seen["q"] == "airport" and seen["limit"] == "3"
    assert seen["lat"] == "20.3" and seen["lon"] == "85.8"
    assert len(res) == 1  # feature with no name/street is skipped
    assert res[0].label == "Biju Patnaik International Airport"
    assert (res[0].lon, res[0].lat) == (85.8134847, 20.2522954)
    assert "Odisha" in res[0].address


def test_photon_omits_bias_when_absent(monkeypatch):
    seen = {}

    def handler(request: httpx.Request):
        seen.update(request.url.params)
        return httpx.Response(200, json=_PHOTON_BODY)

    run(_photon_with_transport(monkeypatch, handler).geocode("airport"))
    assert "lat" not in seen and "lon" not in seen


def test_photon_timeout_and_http_error_become_provider_error(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(RoutingProviderError):
        run(_photon_with_transport(monkeypatch, timeout).geocode("x"))

    with pytest.raises(RoutingProviderError):
        run(_photon_with_transport(monkeypatch, lambda r: httpx.Response(503)).geocode("x"))


# ---------- endpoint: cache key + 503 signal ----------


def _client(geocoder) -> TestClient:
    app = FastAPI()
    app.include_router(geocode_router.router)
    provider = CompositeProvider(MockRouting(), geocoder)
    app.dependency_overrides[get_routing_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    geocode_router._CACHE.clear()
    yield
    geocode_router._CACHE.clear()


def test_cache_key_includes_rounded_bias():
    mk = geocode_router.make_cache_key
    rb = geocode_router._round_bias
    assert mk("Cafe ", None) == "cafe"
    assert mk("cafe", rb(20.31, 85.82)) == mk("CAFE", rb(20.34, 85.79))  # tiny pan -> same key
    assert mk("cafe", rb(20.3, 85.8)) != mk("cafe", rb(28.6, 77.2))  # different viewport
    assert mk("cafe", rb(20.3, 85.8)) != mk("cafe", None)
    assert rb(20.3, None) is None


def test_endpoint_caches_per_viewport():
    geo = FakeGeocoder()
    client = _client(geo)

    client.get("/api/geocode", params={"q": "cafe", "lat": 20.31, "lon": 85.82})
    client.get("/api/geocode", params={"q": "cafe", "lat": 20.33, "lon": 85.84})  # cache hit
    assert len(geo.calls) == 1

    r = client.get("/api/geocode", params={"q": "cafe", "lat": 28.6, "lon": 77.2})  # other city
    assert len(geo.calls) == 2
    assert geo.calls[1][2:] == (28.6, 77.2)  # rounded bias is what the provider sees
    assert r.status_code == 200

    client.get("/api/geocode", params={"q": "cafe"})  # no bias is its own key
    assert len(geo.calls) == 3
    client.get("/api/geocode", params={"q": "cafe"})
    assert len(geo.calls) == 3


def test_endpoint_works_with_mock_provider():
    r = _client(MockGeocoding()).get("/api/geocode", params={"q": "Station", "lat": 20.3, "lon": 85.8})
    assert r.status_code == 200 and r.json()[0]["label"] == "Station"


def test_endpoint_falls_back_without_error():
    geo = FallbackGeocoding(FakeGeocoder(fail=True, label="photon"), FakeGeocoder(label="nominatim"))
    r = _client(geo).get("/api/geocode", params={"q": "cafe", "lat": 20.3, "lon": 85.8})
    assert r.status_code == 200
    assert r.json()[0]["label"] == "nominatim:cafe"


def test_endpoint_signals_slow_when_both_fail_and_does_not_cache():
    photon, nominatim = FakeGeocoder(fail=True), FakeGeocoder(fail=True)
    client = _client(FallbackGeocoding(photon, nominatim))

    r = client.get("/api/geocode", params={"q": "cafe"})
    assert r.status_code == 503
    assert r.json()["detail"] == geocode_router.GEOCODE_UNAVAILABLE_DETAIL

    client.get("/api/geocode", params={"q": "cafe"})
    assert len(photon.calls) == 2  # failure was not cached

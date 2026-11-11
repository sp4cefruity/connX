"""Hosted-demo hardening: per-IP rate limits, the secure cookie flag, and
Nominatim's one-at-a-time requests. No network."""
import asyncio

import httpx
import pytest
from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient

from app import auth, ratelimit
from app.config import Settings, get_settings
from app.ratelimit import rate_limit
from app.routing import nominatim
from app.routing.nominatim import NominatimGeocoding


def _limited_app(environment: str, per_min: int = 3) -> TestClient:
    app = FastAPI()

    @app.get("/limited", dependencies=[Depends(rate_limit("test", "rate_limit_routes_per_min"))])
    def limited():
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: Settings(
        environment=environment, rate_limit_routes_per_min=per_min
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_hits():
    ratelimit._hits.clear()
    yield
    ratelimit._hits.clear()


def test_rate_limit_blocks_after_limit_in_production():
    client = _limited_app("production")
    for _ in range(3):
        assert client.get("/limited").status_code == 200
    r = client.get("/limited")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_rate_limit_is_off_in_development():
    client = _limited_app("development")
    assert all(client.get("/limited").status_code == 200 for _ in range(10))


def test_rate_limit_counts_each_forwarded_ip_separately():
    client = _limited_app("production")
    for _ in range(3):
        client.get("/limited", headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.1"})
    assert client.get("/limited", headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.get("/limited", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_rate_limit_window_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    client = _limited_app("production")
    for _ in range(3):
        client.get("/limited")
    assert client.get("/limited").status_code == 429
    now[0] += 61
    assert client.get("/limited").status_code == 200


@pytest.mark.parametrize("environment,secure", [("production", True), ("development", False)])
def test_device_cookie_is_secure_only_outside_development(monkeypatch, environment, secure):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(environment=environment))

    class _Db:
        def get(self, *_):
            return None

        def add(self, user):
            user.id = "u1"

        def commit(self):
            pass

        def refresh(self, _):
            pass

    response = Response()
    auth.get_or_create_user(response, connx_device=None, db=_Db())
    cookie = response.headers["set-cookie"].lower()
    assert ("secure" in cookie) is secure


def test_nominatim_biased_search_never_overlaps_requests(monkeypatch):
    in_flight = 0
    peak = 0
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak, calls
        calls += 1
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json=[{"name": "Cafe", "display_name": "Cafe, Town", "lon": "85.8", "lat": "20.3"}])

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        nominatim.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )

    geo = NominatimGeocoding("https://nominatim.test", "ConnX-test")
    results = asyncio.run(geo.geocode("cafe", lat=20.3, lon=85.8))

    assert results and results[0].label == "Cafe"
    assert calls == len(nominatim._RING_HALF_SPANS_DEG)
    assert peak == 1


def test_nominatim_spaces_requests_by_min_interval(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        nominatim.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setattr(nominatim.asyncio, "sleep", fake_sleep)

    geo = NominatimGeocoding("https://nominatim.test", "ConnX-test", min_interval_s=1.0)

    async def two():
        await geo.geocode("a")
        await geo.geocode("b")

    asyncio.run(two())
    assert len(sleeps) == 1 and 0.5 < sleeps[0] <= 1.0

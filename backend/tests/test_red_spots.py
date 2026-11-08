"""Red spots: hit-detection boundary, radius validation, CRUD ownership, and
the Route-A-only rule on /compare. In-memory SQLite and a stub router; no network."""
import math
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import SavedLocation
from app.routers import red_spots as red_spots_router
from app.routers import routes as routes_router
from app.routing import CompositeProvider, get_routing_provider
from app.routing.mock import MockGeocoding
from app.schemas import (
    MAX_RADIUS_M,
    MIN_RADIUS_M,
    LonLat,
    RedSpotCreate,
    RedSpotUpdate,
    RouteResult,
)
from app.services.redspots import find_red_spot_hits

_M_PER_DEG_LAT = 111_320.0
LAT0, LON0 = 20.30, 85.82


def _offset_east_lon(distance_m: float, lat: float = LAT0) -> float:
    """Longitude of a point `distance_m` east of LON0 at `lat`."""
    return LON0 + distance_m / (_M_PER_DEG_LAT * math.cos(math.radians(lat)))


def _north_south_route() -> list[LonLat]:
    """~2.2 km straight north-south line at LON0, centred on LAT0."""
    return [LonLat(lon=LON0, lat=LAT0 + d) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]


def _spot(distance_east_m: float, radius_m: float, name: str = "Priya's house") -> SavedLocation:
    return SavedLocation(
        id="11111111-1111-1111-1111-111111111111",
        user_id="u",
        name=name,
        latitude=LAT0,
        longitude=_offset_east_lon(distance_east_m),
        radius_m=radius_m,
        temporary=False,
        created_at=datetime(2026, 1, 1),
    )


# ---------- hit detection boundary ----------


def test_spot_just_inside_radius_is_a_hit():
    [hit] = find_red_spot_hits(_north_south_route(), [_spot(distance_east_m=99, radius_m=100)])
    assert hit.intersects is True
    assert hit.min_distance_m == pytest.approx(99, abs=0.5)


def test_spot_just_outside_radius_is_not_a_hit():
    [hit] = find_red_spot_hits(_north_south_route(), [_spot(distance_east_m=101, radius_m=100)])
    assert hit.intersects is False
    assert hit.min_distance_m == pytest.approx(101, abs=0.5)


def test_spot_far_off_the_path_is_not_a_hit():
    [hit] = find_red_spot_hits(_north_south_route(), [_spot(distance_east_m=5000, radius_m=2000)])
    assert hit.intersects is False
    assert hit.min_distance_m > 2000


def test_spot_centred_on_the_path_reports_zero_distance():
    [hit] = find_red_spot_hits(_north_south_route(), [_spot(distance_east_m=0, radius_m=MIN_RADIUS_M)])
    assert hit.intersects is True
    assert hit.min_distance_m == pytest.approx(0, abs=0.5)


def test_boundary_holds_at_the_radius_limits():
    route = _north_south_route()
    for radius in (MIN_RADIUS_M, MAX_RADIUS_M):
        [inside] = find_red_spot_hits(route, [_spot(radius - 1, radius)])
        [outside] = find_red_spot_hits(route, [_spot(radius + 1, radius)])
        assert inside.intersects is True
        assert outside.intersects is False


# ---------- radius validation (schema) ----------


@pytest.mark.parametrize("radius", [MIN_RADIUS_M, 100, MAX_RADIUS_M])
def test_create_accepts_radius_within_limits(radius):
    spot = RedSpotCreate(name="Home", latitude=LAT0, longitude=LON0, radius_m=radius)
    assert spot.radius_m == radius


@pytest.mark.parametrize("radius", [0, 49.9, MAX_RADIUS_M + 0.1, 5000, -10])
def test_create_rejects_radius_outside_limits(radius):
    with pytest.raises(ValidationError):
        RedSpotCreate(name="Home", latitude=LAT0, longitude=LON0, radius_m=radius)


@pytest.mark.parametrize("radius", [49, 2001])
def test_update_rejects_radius_outside_limits(radius):
    with pytest.raises(ValidationError):
        RedSpotUpdate(radius_m=radius)


def test_update_rejects_null_for_required_fields():
    for field in ("name", "latitude", "longitude", "radius_m"):
        with pytest.raises(ValidationError):
            RedSpotUpdate(**{field: None})


def test_name_must_not_be_blank():
    with pytest.raises(ValidationError):
        RedSpotCreate(name="   ", latitude=LAT0, longitude=LON0, radius_m=100)


# ---------- API: limits, CRUD, per-cookie persistence ----------


class StubRouting:
    """Returns a fixed north-south line for starts at LON0, an east-shifted one otherwise."""

    def __init__(self, geometries: dict[float, list[LonLat]]):
        self.geometries = geometries  # keyed by start.lon

    async def get_route(self, start, end, mode):
        return RouteResult(distance_km=2.2, duration_min=5, geometry=self.geometries[start.lon], mode=mode)

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [await self.get_route(start, end, mode)]


@pytest.fixture
def make_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def get_test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def factory(routing=None) -> TestClient:
        app = FastAPI()
        app.include_router(red_spots_router.router)
        app.include_router(routes_router.router)
        app.dependency_overrides[get_db] = get_test_db
        if routing is not None:
            provider = CompositeProvider(routing, MockGeocoding())
            app.dependency_overrides[get_routing_provider] = lambda: provider
        return TestClient(app)

    return factory


def _payload(**over):
    body = {"name": "Priya's house", "latitude": LAT0, "longitude": LON0, "radius_m": 150}
    body.update(over)
    return body


def test_api_rejects_out_of_range_radius_on_create_and_update(make_client):
    client = make_client()
    assert client.post("/api/red-spots", json=_payload(radius_m=49)).status_code == 422
    assert client.post("/api/red-spots", json=_payload(radius_m=2001)).status_code == 422
    assert client.get("/api/red-spots").json() == []

    created = client.post("/api/red-spots", json=_payload(radius_m=50))
    assert created.status_code == 201
    spot_id = created.json()["id"]

    assert client.put(f"/api/red-spots/{spot_id}", json={"radius_m": 2001}).status_code == 422
    assert client.put(f"/api/red-spots/{spot_id}", json={"radius_m": 10}).status_code == 422
    assert client.get("/api/red-spots").json()[0]["radius_m"] == 50  # untouched by rejected updates

    ok = client.put(f"/api/red-spots/{spot_id}", json={"radius_m": 2000})
    assert ok.status_code == 200 and ok.json()["radius_m"] == 2000


def test_api_rename_move_resize_delete(make_client):
    client = make_client()
    spot_id = client.post("/api/red-spots", json=_payload()).json()["id"]

    updated = client.put(
        f"/api/red-spots/{spot_id}",
        json={"name": "Priya's flat", "latitude": LAT0 + 0.001, "longitude": LON0 + 0.001, "radius_m": 300},
    ).json()
    assert updated["name"] == "Priya's flat"
    assert updated["latitude"] == pytest.approx(LAT0 + 0.001)
    assert updated["longitude"] == pytest.approx(LON0 + 0.001)
    assert updated["radius_m"] == 300

    # a partial update leaves the other fields alone
    renamed = client.put(f"/api/red-spots/{spot_id}", json={"name": "Home"}).json()
    assert renamed["name"] == "Home" and renamed["radius_m"] == 300

    assert client.delete(f"/api/red-spots/{spot_id}").status_code == 204
    assert client.get("/api/red-spots").json() == []
    assert client.delete(f"/api/red-spots/{spot_id}").status_code == 404


def test_spots_persist_per_cookie_and_are_private(make_client):
    client = make_client()
    client.post("/api/red-spots", json=_payload())
    device_cookie = client.cookies.get("connx_device")
    assert device_cookie

    # a "reload": a fresh client presenting the same cookie sees the spot
    reloaded = TestClient(client.app)  # same app + DB, empty cookie jar
    reloaded.cookies.set("connx_device", device_cookie)
    assert [s["name"] for s in reloaded.get("/api/red-spots").json()] == ["Priya's house"]

    # a different browser (no cookie) gets its own empty list and can't touch ours
    other = TestClient(client.app)
    assert other.get("/api/red-spots").json() == []
    spot_id = client.get("/api/red-spots").json()[0]["id"]
    assert other.put(f"/api/red-spots/{spot_id}", json={"name": "x"}).status_code == 404
    assert other.delete(f"/api/red-spots/{spot_id}").status_code == 404


# ---------- Route A only ----------


def test_compare_checks_red_spots_against_route_a_only(make_client):
    route_a = _north_south_route()  # at LON0
    far_lon = _offset_east_lon(3000)
    route_b = [LonLat(lon=far_lon, lat=p.lat) for p in route_a]
    routing = StubRouting({LON0: route_a, far_lon: route_b})
    client = make_client(routing)

    # spot sits on Route B's path, ~3 km from Route A
    client.post("/api/red-spots", json=_payload(longitude=far_lon, radius_m=200))
    # spot sits on Route A's path
    client.post("/api/red-spots", json=_payload(name="On A", longitude=LON0, radius_m=200))

    body = {
        "primary_start": {"lon": LON0, "lat": LAT0},
        "primary_end": {"lon": LON0, "lat": LAT0 + 0.01},
        "comparison_start": {"lon": far_lon, "lat": LAT0},
        "comparison_end": {"lon": far_lon, "lat": LAT0 + 0.01},
    }
    resp = client.post("/api/routes/compare", json=body)
    assert resp.status_code == 200
    hits = {h["red_spot"]["name"]: h for h in resp.json()["red_spots"]}

    assert hits["On A"]["intersects"] is True
    assert hits["Priya's house"]["intersects"] is False
    assert hits["Priya's house"]["min_distance_m"] == pytest.approx(3000, abs=5)

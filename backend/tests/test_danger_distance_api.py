"""Compare / recommend accept `danger_distance_m` (50-1000 m, default 200) and
the removed `sensitivity` field is gone. Overlap never depends on the danger
distance (ADR 0001)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from shapely.geometry import shape

from app.auth import get_or_create_user
from app.config import Settings
from app.database import get_db
from app.routers import routes as routes_router
from app.routing import get_routing_provider
from app.routing.base import RoutingProviderError
from app.schemas import CompareRequest, LonLat, RecommendRequest, RouteResult

A_START, A_END = {"lon": 85.800, "lat": 20.290}, {"lon": 85.820, "lat": 20.290}
# Route B runs ~55 m north of A: a near-miss, never the "same road".
B_START, B_END = {"lon": 85.800, "lat": 20.2905}, {"lon": 85.820, "lat": 20.2905}


def _compare_body(**extra):
    return {
        "primary_start": A_START,
        "primary_end": A_END,
        "comparison_start": B_START,
        "comparison_end": B_END,
        "include_red_spots": False,
        **extra,
    }


def _recommend_body(**extra):
    return {
        "primary_start": A_START,
        "primary_end": A_END,
        "comparison_start": B_START,
        "comparison_end": B_END,
        "avoid_red_spots": False,
        **extra,
    }


# ---------- schema validation ----------


@pytest.mark.parametrize("model,body", [(CompareRequest, _compare_body), (RecommendRequest, _recommend_body)])
class TestDangerDistanceValidation:
    def test_defaults_to_200m(self, model, body):
        assert model(**body()).danger_distance_m == 200

    @pytest.mark.parametrize("value", [50, 200, 999.5, 1000])
    def test_accepts_values_in_range(self, model, body, value):
        assert model(**body(danger_distance_m=value)).danger_distance_m == value

    @pytest.mark.parametrize("value", [0, -10, 49.9, 1000.1, 5000])
    def test_rejects_values_out_of_range(self, model, body, value):
        with pytest.raises(ValidationError):
            model(**body(danger_distance_m=value))

    def test_sensitivity_is_no_longer_a_field(self, model, body):
        assert "sensitivity" not in model.model_fields


def test_sensitivity_presets_removed_from_config():
    fields = Settings.model_fields
    assert "overlap_sensitivity_presets" not in fields
    assert fields["overlap_tolerance_m"].default == 25.0


# ---------- endpoints ----------


class _StubProvider:
    """Straight-line routes, no network."""

    async def get_route(self, start, end, mode):
        return RouteResult(
            distance_km=1.9,
            duration_min=4.0,
            geometry=[LonLat(lon=start.lon, lat=start.lat), LonLat(lon=end.lon, lat=end.lat)],
            mode=mode,
        )

    async def get_alternative_routes(self, start, end, mode, count=3):
        return [await self.get_route(start, end, mode)]

    async def get_route_via(self, start, via, end, mode):
        raise RoutingProviderError("this stub cannot route via a waypoint")

    async def get_route_avoiding(self, start, end, mode, avoid):
        raise RoutingProviderError("this stub cannot route around an area")


class _FakeUser:
    id = "user-1"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_router.router)
    app.dependency_overrides[get_routing_provider] = lambda: _StubProvider()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_or_create_user] = lambda: _FakeUser()
    return TestClient(app)


@pytest.mark.parametrize("bad", [49, 1001, "wide"])
def test_compare_endpoint_rejects_invalid_danger_distance(client, bad):
    res = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=bad))
    assert res.status_code == 422


@pytest.mark.parametrize("bad", [49, 1001])
def test_recommend_endpoint_rejects_invalid_danger_distance(client, bad):
    res = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=bad))
    assert res.status_code == 422


def test_compare_works_without_danger_distance_and_without_sensitivity(client):
    res = client.post("/api/routes/compare", json=_compare_body())
    assert res.status_code == 200


def test_compare_overlap_unchanged_but_band_changes_with_danger_distance(client):
    near = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=50)).json()
    far = client.post("/api/routes/compare", json=_compare_body(danger_distance_m=900)).json()

    assert near["overlap"] == far["overlap"]
    assert near["overlap"]["percentage"] == 0  # ~55 m apart: a near-miss, not overlap

    near_band, far_band = shape(near["red_zone_band"]), shape(far["red_zone_band"])
    assert far_band.area > near_band.area * 4


def test_recommend_overlap_unchanged_but_band_changes_with_danger_distance(client):
    near = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=50)).json()
    far = client.post("/api/routes/recommend", json=_recommend_body(danger_distance_m=900)).json()

    assert [r["overlap"] for r in near["routes"]] == [r["overlap"] for r in far["routes"]]
    assert shape(far["red_zone_band"]).area > shape(near["red_zone_band"]).area * 4


def test_recommend_without_comparison_route_has_no_band(client):
    body = _recommend_body()
    body["comparison_start"] = body["comparison_end"] = None
    res = client.post("/api/routes/recommend", json=body)
    assert res.status_code == 200
    assert res.json()["red_zone_band"] is None

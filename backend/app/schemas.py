from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TravelMode = Literal["driving", "walking", "cycling"]

# Danger distance bounds in metres (ADR 0001): the user-set width of the Red
# zone band. Separate from the fixed overlap tolerance.
DANGER_DISTANCE_MIN_M = 50.0
DANGER_DISTANCE_MAX_M = 1000.0
DANGER_DISTANCE_DEFAULT_M = 200.0


def _danger_distance_field():
    return Field(
        default=DANGER_DISTANCE_DEFAULT_M, ge=DANGER_DISTANCE_MIN_M, le=DANGER_DISTANCE_MAX_M
    )


# ---------- shared geo primitives ----------

class LonLat(BaseModel):
    lon: float
    lat: float


class GeocodeResult(BaseModel):
    label: str
    address: str | None = None
    lon: float
    lat: float


# ---------- routing ----------

class RouteRequest(BaseModel):
    start: LonLat
    end: LonLat
    mode: TravelMode = "driving"


class AlternativesRequest(RouteRequest):
    count: int = Field(default=3, ge=1, le=6)


class RouteResult(BaseModel):
    distance_km: float
    duration_min: float
    geometry: list[LonLat]  # ordered polyline vertices
    mode: TravelMode


# ---------- overlap ----------

class OverlapSegment(BaseModel):
    type: Literal["crossing", "shared_segment"]
    distance_m: float
    geometry: list[LonLat]
    start_fraction: float  # 0..1 position along route A
    end_fraction: float


class OverlapResult(BaseModel):
    distance_km: float
    percentage: float
    duration_min: float
    segments: list[OverlapSegment]


# ---------- red spots ----------

class RedSpotBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_m: float = 100.0
    type: str | None = None
    temporary: bool = False
    expires_at: datetime | None = None


class RedSpotCreate(RedSpotBase):
    pass


class RedSpotUpdate(BaseModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_m: float | None = None
    type: str | None = None
    temporary: bool | None = None
    expires_at: datetime | None = None


class RedSpot(RedSpotBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RedSpotHit(BaseModel):
    red_spot: RedSpot
    intersects: bool
    min_distance_m: float


# ---------- compare / recommend ----------

class CompareRequest(BaseModel):
    primary_start: LonLat
    primary_end: LonLat
    comparison_start: LonLat
    comparison_end: LonLat
    mode: TravelMode = "driving"
    danger_distance_m: float = _danger_distance_field()
    include_red_spots: bool = True


class GeoJsonPolygon(BaseModel):
    """GeoJSON Polygon / MultiPolygon geometry, coordinates in [lon, lat]."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list


class CompareResponse(BaseModel):
    primary_route: RouteResult
    comparison_route: RouteResult
    overlap: OverlapResult
    red_zone_band: GeoJsonPolygon | None = None
    red_spots: list[RedSpotHit]


class RouteScoreBreakdown(BaseModel):
    time_penalty: float
    overlap_penalty: float
    red_zone_penalty: float
    distance_penalty: float
    total: float


class ScoredRoute(BaseModel):
    tier: Literal["recommended", "alternative", "fastest"]
    route: RouteResult
    overlap: OverlapResult
    red_spot_hits: list[RedSpotHit]
    score: RouteScoreBreakdown
    explanation: list[str]


class RecommendRequest(BaseModel):
    primary_start: LonLat
    primary_end: LonLat
    comparison_start: LonLat | None = None
    comparison_end: LonLat | None = None
    mode: TravelMode = "driving"
    danger_distance_m: float = _danger_distance_field()
    avoid_overlap: bool = True
    avoid_red_spots: bool = True
    alternatives_count: int = Field(default=3, ge=1, le=6)


class RecommendResponse(BaseModel):
    routes: list[ScoredRoute]
    recommended_index: int
    comparison_route: RouteResult | None = None
    red_zone_band: GeoJsonPolygon | None = None

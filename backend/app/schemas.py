from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TravelMode = Literal["driving", "walking", "cycling"]
Sensitivity = Literal["low", "medium", "high"]


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

# Red spot radius limits (CONTEXT.md: 50 m-2 km). The frontend mirrors these.
MIN_RADIUS_M = 50.0
MAX_RADIUS_M = 2000.0


class RedSpotBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_m: float = 100.0
    type: str | None = None
    temporary: bool = False
    expires_at: datetime | None = None


class RedSpotCreate(RedSpotBase):
    # Limits are enforced on input only; reading back never re-validates them.
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=100.0, ge=MIN_RADIUS_M, le=MAX_RADIUS_M)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class RedSpotUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_m: float | None = Field(default=None, ge=MIN_RADIUS_M, le=MAX_RADIUS_M)
    type: str | None = None
    temporary: bool | None = None
    expires_at: datetime | None = None

    @field_validator("name", "latitude", "longitude", "radius_m", "temporary")
    @classmethod
    def _not_null(cls, v):
        # Omit a field to leave it alone; an explicit null would hit a NOT NULL column.
        if v is None:
            raise ValueError("must not be null")
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


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
    sensitivity: Sensitivity = "medium"
    include_red_spots: bool = True


class CompareResponse(BaseModel):
    primary_route: RouteResult
    comparison_route: RouteResult
    overlap: OverlapResult
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
    sensitivity: Sensitivity = "medium"
    avoid_overlap: bool = True
    avoid_red_spots: bool = True
    alternatives_count: int = Field(default=3, ge=1, le=6)


class RecommendResponse(BaseModel):
    routes: list[ScoredRoute]
    recommended_index: int
    comparison_route: RouteResult | None = None

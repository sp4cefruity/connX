from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_or_create_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.routers.red_spots import get_active_red_spots
from app.routing import get_routing_provider
from app.routing.base import RoutingProvider, RoutingProviderError
from app.schemas import (
    AlternativesRequest,
    CompareRequest,
    CompareResponse,
    OverlapResult,
    RecommendRequest,
    RecommendResponse,
    RouteRequest,
    RouteResult,
    ScoredRoute,
)
from app.services import scoring
from app.services.overlap import compute_overlap
from app.services.redspots import find_red_spot_hits

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("", response_model=RouteResult)
async def calculate_route(
    payload: RouteRequest, provider: RoutingProvider = Depends(get_routing_provider)
):
    try:
        return await provider.get_route(payload.start, payload.end, payload.mode)
    except RoutingProviderError as exc:
        raise HTTPException(status_code=502, detail="Couldn't find a route between these locations.") from exc


@router.post("/alternatives", response_model=list[RouteResult])
async def calculate_alternatives(
    payload: AlternativesRequest, provider: RoutingProvider = Depends(get_routing_provider)
):
    try:
        routes = await provider.get_alternative_routes(payload.start, payload.end, payload.mode, payload.count)
    except RoutingProviderError as exc:
        raise HTTPException(status_code=502, detail="Couldn't find routes between these locations.") from exc
    if not routes:
        raise HTTPException(status_code=404, detail="We found a route, but no meaningful alternatives were available.")
    return routes


@router.post("/compare", response_model=CompareResponse)
async def compare_routes(
    payload: CompareRequest,
    provider: RoutingProvider = Depends(get_routing_provider),
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_user),
    settings: Settings = Depends(get_settings),
):
    try:
        primary = await provider.get_route(payload.primary_start, payload.primary_end, payload.mode)
        comparison = await provider.get_route(payload.comparison_start, payload.comparison_end, payload.mode)
    except RoutingProviderError as exc:
        raise HTTPException(status_code=502, detail="Couldn't find a route between these locations.") from exc

    tolerance_m = settings.overlap_sensitivity_presets[payload.sensitivity]
    overlap = compute_overlap(
        route_a_geometry=primary.geometry,
        route_a_duration_min=primary.duration_min,
        route_b_geometry=comparison.geometry,
        tolerance_m=tolerance_m,
        min_meaningful_overlap_m=settings.min_meaningful_overlap_m,
        merge_gap_m=settings.overlap_merge_gap_m,
    )

    red_spot_hits = []
    if payload.include_red_spots:
        spots = get_active_red_spots(db, user.id)
        red_spot_hits = find_red_spot_hits(primary.geometry, spots)

    return CompareResponse(
        primary_route=primary,
        comparison_route=comparison,
        overlap=overlap,
        red_spots=red_spot_hits,
    )


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_route(
    payload: RecommendRequest,
    provider: RoutingProvider = Depends(get_routing_provider),
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_user),
    settings: Settings = Depends(get_settings),
):
    """
    The alternative-route engine (spec §13, §33, §34): fetch several
    candidate routes for the primary trip, score each against the
    comparison route's overlap and the user's red spots, and return them
    ranked with the best one flagged as recommended.
    """
    try:
        candidates = await provider.get_alternative_routes(
            payload.primary_start, payload.primary_end, payload.mode, payload.alternatives_count
        )
    except RoutingProviderError as exc:
        raise HTTPException(status_code=502, detail="Couldn't find a route between these locations.") from exc
    if not candidates:
        raise HTTPException(status_code=404, detail="We found a route, but no meaningful alternatives were available.")

    comparison = None
    if payload.comparison_start and payload.comparison_end:
        try:
            comparison = await provider.get_route(payload.comparison_start, payload.comparison_end, payload.mode)
        except RoutingProviderError:
            comparison = None

    spots = get_active_red_spots(db, user.id) if payload.avoid_red_spots else []

    tolerance_m = settings.overlap_sensitivity_presets[payload.sensitivity]
    fastest_duration = min(c.duration_min for c in candidates)
    shortest_distance = min(c.distance_km for c in candidates)
    fastest_route = min(candidates, key=lambda c: c.duration_min)

    scored: list[ScoredRoute] = []
    for candidate in candidates:
        if comparison:
            overlap = compute_overlap(
                route_a_geometry=candidate.geometry,
                route_a_duration_min=candidate.duration_min,
                route_b_geometry=comparison.geometry,
                tolerance_m=tolerance_m,
                min_meaningful_overlap_m=settings.min_meaningful_overlap_m,
                merge_gap_m=settings.overlap_merge_gap_m,
            )
        else:
            overlap = OverlapResult(distance_km=0, percentage=0, duration_min=0, segments=[])

        red_spot_hits = find_red_spot_hits(candidate.geometry, spots)

        score = scoring.score_route(
            scoring.ScoringInputs(
                route=candidate,
                overlap=overlap,
                red_spot_hits=red_spot_hits,
                avoid_overlap=payload.avoid_overlap,
                avoid_red_spots=payload.avoid_red_spots,
                fastest_duration_min=fastest_duration,
                shortest_distance_km=shortest_distance,
            )
        )
        explanation = scoring.explain(candidate, overlap, red_spot_hits, fastest_route)

        scored.append(
            ScoredRoute(
                tier="alternative",  # tiers assigned below once we know rank + fastest
                route=candidate,
                overlap=overlap,
                red_spot_hits=red_spot_hits,
                score=score,
                explanation=explanation,
            )
        )

    scored.sort(key=lambda s: s.score.total)

    for s in scored:
        s.tier = "alternative"
    scored[0].tier = "recommended"
    fastest_in_scored = min(scored, key=lambda s: s.route.duration_min)
    if fastest_in_scored is not scored[0]:
        fastest_in_scored.tier = "fastest"

    recommended_index = next(i for i, s in enumerate(scored) if s.tier == "recommended")

    return RecommendResponse(routes=scored, recommended_index=recommended_index, comparison_route=comparison)

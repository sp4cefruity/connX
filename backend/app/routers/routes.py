import asyncio
from dataclasses import dataclass

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
    Encounter,
    OverlapResult,
    RecommendRequest,
    RecommendResponse,
    RedSpotHit,
    RouteRequest,
    RouteResult,
    ScoredRoute,
)
from app.services import detours, scoring
from app.services.encounters import compute_encounters
from app.services.overlap import compute_overlap
from app.services.red_zone import build_red_zone_band
from app.services.redspots import find_red_spot_hits

router = APIRouter(prefix="/api/routes", tags=["routes"])

# Most extra routing calls one /recommend may spend on detours (ORS free tier
# is 2,000 a day; the route cache absorbs repeats).
MAX_DETOUR_CALLS = 3
NO_BETTER_ROUTE = "No better route found nearby"
_NO_OVERLAP = OverlapResult(distance_km=0, percentage=0, duration_min=0, segments=[])


@dataclass
class _Analysed:
    """A candidate route with everything scoring needs to know about it."""

    route: RouteResult
    overlap: OverlapResult
    encounters: list[Encounter]
    red_spot_hits: list[RedSpotHit]


def _rank(items: list[_Analysed], payload: RecommendRequest, has_comparison: bool) -> list[ScoredRoute]:
    """Score every candidate against the others, best first, with tiers set."""
    fastest_route = min((a.route for a in items), key=lambda r: r.duration_min)
    shortest_distance = min(a.route.distance_km for a in items)

    scored: list[ScoredRoute] = []
    for a in items:
        score = scoring.score_route(
            scoring.ScoringInputs(
                route=a.route,
                overlap=a.overlap,
                red_spot_hits=a.red_spot_hits,
                avoid_overlap=payload.avoid_overlap,
                avoid_red_spots=payload.avoid_red_spots,
                fastest_duration_min=fastest_route.duration_min,
                shortest_distance_km=shortest_distance,
                encounters=a.encounters,
                danger_distance_m=payload.danger_distance_m,
            )
        )
        explanation = scoring.explain(
            a.route,
            a.overlap,
            a.red_spot_hits,
            fastest_route,
            a.encounters if has_comparison else None,
            payload.danger_distance_m,
        )
        scored.append(
            ScoredRoute(
                tier="alternative",  # tiers assigned below once we know rank + fastest
                route=a.route,
                overlap=a.overlap,
                encounters=a.encounters,
                red_spot_hits=a.red_spot_hits,
                score=score,
                explanation=explanation,
            )
        )

    scored.sort(key=lambda s: s.score.total)
    scored[0].tier = "recommended"
    fastest_in_scored = min(scored, key=lambda s: s.route.duration_min)
    if fastest_in_scored is not scored[0]:
        fastest_in_scored.tier = "fastest"
    return scored


def _trouble(overlap: OverlapResult, encounters: list[Encounter], hits: list[RedSpotHit], payload: RecommendRequest) -> detours.Trouble:
    """What a route runs into, counting only what the user asked to avoid."""
    return detours.Trouble(
        shared_km=overlap.distance_km if payload.avoid_overlap else 0.0,
        close_passes=len(encounters) if payload.avoid_overlap else 0,
        red_spot_hits=sum(1 for h in hits if h.intersects) if payload.avoid_red_spots else 0,
    )


def _has_trouble(best: ScoredRoute, payload: RecommendRequest) -> bool:
    """Is there anything on `best` that the user asked us to avoid?"""
    t = _trouble(best.overlap, best.encounters, best.red_spot_hits, payload)
    return bool(t.shared_km or t.close_passes or t.red_spot_hits)


async def _route_avoiding(provider: RoutingProvider, payload: RecommendRequest, zone: dict) -> RouteResult | None:
    try:
        return await provider.get_route_avoiding(payload.primary_start, payload.primary_end, payload.mode, zone)
    except RoutingProviderError:
        return None  # unsupported, over a size limit, or no route around it


async def _route_via(provider: RoutingProvider, payload: RecommendRequest, via) -> RouteResult | None:
    try:
        return await provider.get_route_via(payload.primary_start, via, payload.primary_end, payload.mode)
    except RoutingProviderError:
        return None  # a failed detour just means one candidate fewer


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

    # Overlap uses the fixed tolerance only; the danger distance just sizes
    # the red zone band (ADR 0001).
    overlap = compute_overlap(
        route_a_geometry=primary.geometry,
        route_a_duration_min=primary.duration_min,
        route_b_geometry=comparison.geometry,
        tolerance_m=settings.overlap_tolerance_m,
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
        red_zone_band=build_red_zone_band(comparison.geometry, payload.danger_distance_m),
        encounters=compute_encounters(
            primary.geometry,
            comparison.geometry,
            payload.danger_distance_m,
            overlap.segments,
            settings.overlap_merge_gap_m,
        ),
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

    def analyse(route: RouteResult) -> _Analysed:
        if comparison:
            overlap = compute_overlap(
                route_a_geometry=route.geometry,
                route_a_duration_min=route.duration_min,
                route_b_geometry=comparison.geometry,
                tolerance_m=settings.overlap_tolerance_m,
                min_meaningful_overlap_m=settings.min_meaningful_overlap_m,
                merge_gap_m=settings.overlap_merge_gap_m,
            )
            encounters = compute_encounters(
                route.geometry,
                comparison.geometry,
                payload.danger_distance_m,
                overlap.segments,
                settings.overlap_merge_gap_m,
            )
        else:
            overlap = _NO_OVERLAP
            encounters = []
        return _Analysed(route, overlap, encounters, find_red_spot_hits(route.geometry, spots))

    analysed = [analyse(c) for c in candidates]
    scored = _rank(analysed, payload, has_comparison=comparison is not None)

    # The providers often return a single route, and every alternative shares
    # its roads. If the best one still has trouble on it, build detours
    # ourselves and let scoring judge them.
    detours_wanted = min(MAX_DETOUR_CALLS, payload.alternatives_count - len(candidates))
    if detours_wanted > 0 and _has_trouble(scored[0], payload):
        best = scored[0]
        avoiding_b = comparison is not None and payload.avoid_overlap
        best_overlap = best.overlap if avoiding_b else _NO_OVERLAP
        circles = [
            detours.AvoidCircle(h.red_spot.longitude, h.red_spot.latitude, h.red_spot.radius_m)
            for h in best.red_spot_hits
            if payload.avoid_red_spots and h.intersects
        ]
        baseline = _trouble(best.overlap, best.encounters, best.red_spot_hits, payload)

        def improving(routes: list[RouteResult]) -> list[_Analysed]:
            """Detours worth offering: new roads that really get away from the trouble.

            A detour that still runs along Route B is no use even when it is
            longer, and so shares a smaller percentage of its length.
            """
            kept = detours.filter_detours(
                routes,
                candidates,
                tolerance_m=settings.overlap_tolerance_m,
                min_meaningful_overlap_m=settings.min_meaningful_overlap_m,
                merge_gap_m=settings.overlap_merge_gap_m,
            )
            return [
                a
                for a in (analyse(r) for r in kept)
                if detours.improves_on(_trouble(a.overlap, a.encounters, a.red_spot_hits, payload), baseline)
            ]

        tried = False
        better: list[_Analysed] = []

        # 1. Ask the router to keep out of Route B's road and the Red spots.
        #    One call. Only some providers can (ORS) and it refuses trips over
        #    its size limits, so this is best effort.
        zone = detours.build_avoid_zone(
            best.route.geometry, comparison.geometry if avoiding_b else None, circles, best_overlap
        )
        if zone:
            tried = True
            avoided = await _route_avoiding(provider, payload, zone)
            better = improving([avoided] if avoided else [])

        # 2. Otherwise steer with via points beside each trouble stretch.
        if not better:
            waypoints = detours.plan_waypoints(
                route=best.route.geometry,
                avoid_route=comparison.geometry if avoiding_b else None,
                avoid_circles=circles,
                danger_distance_m=payload.danger_distance_m,
                overlap=best_overlap,
                encounters=best.encounters if avoiding_b else [],
                max_waypoints=detours_wanted,
            )
            if waypoints:
                tried = True
                found = await asyncio.gather(*(_route_via(provider, payload, wp) for wp in waypoints))
                better = improving([r for r in found if r is not None])

        if better:
            analysed += better
            scored = _rank(analysed, payload, has_comparison=comparison is not None)
        elif tried:
            best.explanation.append(NO_BETTER_ROUTE)

    recommended_index = next(i for i, s in enumerate(scored) if s.tier == "recommended")

    red_zone_band = build_red_zone_band(comparison.geometry, payload.danger_distance_m) if comparison else None

    return RecommendResponse(
        routes=scored,
        recommended_index=recommended_index,
        comparison_route=comparison,
        red_zone_band=red_zone_band,
    )

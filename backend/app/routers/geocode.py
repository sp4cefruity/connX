"""GET /api/geocode — spec §41. Cached in-memory (spec §47: cache geocoding results).

Optional `lat`/`lon` query params bias results toward the map viewport
(ADR 0003). The bias is rounded and folded into the cache key so results for
different viewports never collide, while tiny pans still hit the cache.

If every geocoding provider fails the endpoint answers 503 with
detail GEOCODE_UNAVAILABLE_DETAIL — a distinct signal the frontend uses to show
a quiet "search is slow right now" state instead of an error.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import TTLCache
from app.routing import get_routing_provider
from app.routing.base import RoutingProvider, RoutingProviderError
from app.schemas import GeocodeResult

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

GEOCODE_UNAVAILABLE_DETAIL = "search_slow"

_CACHE_TTL_S = 60 * 30  # 30 minutes — place search results don't change fast
_CACHE_MAX_ENTRIES = 2000
_CACHE: TTLCache[list[GeocodeResult]] = TTLCache(_CACHE_TTL_S, _CACHE_MAX_ENTRIES)
_BIAS_DECIMALS = 1  # ~11 km: coarse enough that small pans reuse cached results


def _round_bias(lat: float | None, lon: float | None) -> tuple[float, float] | None:
    if lat is None or lon is None:
        return None
    return round(lat, _BIAS_DECIMALS), round(lon, _BIAS_DECIMALS)


def make_cache_key(q: str, bias: tuple[float, float] | None) -> str:
    key = q.strip().lower()
    if bias is None:
        return key
    return f"{key}|{bias[0]:.{_BIAS_DECIMALS}f},{bias[1]:.{_BIAS_DECIMALS}f}"


@router.get("", response_model=list[GeocodeResult])
async def geocode(
    q: str = Query(..., min_length=1, max_length=200),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    provider: RoutingProvider = Depends(get_routing_provider),
):
    bias = _round_bias(lat, lon)
    key = make_cache_key(q, bias)

    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        if bias is None:
            results = await provider.geocode(q)
        else:
            results = await provider.geocode(q, lat=bias[0], lon=bias[1])
    except RoutingProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail=GEOCODE_UNAVAILABLE_DETAIL,
            headers={"Retry-After": "2"},
        ) from exc

    _CACHE.set(key, results)
    return results

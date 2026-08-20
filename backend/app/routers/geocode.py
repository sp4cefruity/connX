"""GET /api/geocode — spec §41. Cached in-memory (spec §47: cache geocoding results)."""
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routing import get_routing_provider
from app.routing.base import RoutingProvider, RoutingProviderError
from app.schemas import GeocodeResult

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

_CACHE: dict[str, tuple[float, list[GeocodeResult]]] = {}
_CACHE_TTL_S = 60 * 30  # 30 minutes — place search results don't change fast


@router.get("", response_model=list[GeocodeResult])
async def geocode(
    q: str = Query(..., min_length=1, max_length=200),
    provider: RoutingProvider = Depends(get_routing_provider),
):
    key = q.strip().lower()
    now = time.time()

    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_S:
        return cached[1]

    try:
        results = await provider.geocode(q)
    except RoutingProviderError as exc:
        raise HTTPException(status_code=502, detail="Couldn't search for that location right now.") from exc

    _CACHE[key] = (now, results)
    return results

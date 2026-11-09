"""
Provider-agnostic wrappers around any routing backend (an object with
get_route / get_alternative_routes): a fallback chain and a result cache.
Neither knows which provider is behind it, so swapping providers stays a
config change (ADR 0005).
"""
import logging

from app.cache import TTLCache
from app.routing.base import RoutingProviderError
from app.schemas import LonLat, RouteResult, TravelMode

log = logging.getLogger(__name__)


class FallbackRouting:
    """Try `primary`; on RoutingProviderError (network, quota, no route) try `fallback`."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        try:
            return await self._primary.get_route(start, end, mode)
        except RoutingProviderError as exc:
            log.warning("primary routing failed (%s); using fallback", exc)
            return await self._fallback.get_route(start, end, mode)

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        try:
            return await self._primary.get_alternative_routes(start, end, mode, count)
        except RoutingProviderError as exc:
            log.warning("primary routing failed (%s); using fallback", exc)
            return await self._fallback.get_alternative_routes(start, end, mode, count)


def _point(p: LonLat) -> tuple[float, float]:
    # 5 decimals is ~1 m: GPS jitter and re-clicks hit the same entry.
    return round(p.lon, 5), round(p.lat, 5)


class CachedRouting:
    """Remembers successful routes. Failures are never cached."""

    def __init__(self, inner, ttl_s: float = 3600.0, max_entries: int = 500):
        self._inner = inner
        self._cache: TTLCache[list[RouteResult]] = TTLCache(ttl_s, max_entries)

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self._cached("route", start, end, mode, 1, self._inner.get_route)
        return routes[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._cached("alts", start, end, mode, count, self._inner.get_alternative_routes)

    async def _cached(self, kind, start, end, mode, count, fetch) -> list[RouteResult]:
        key = (kind, _point(start), _point(end), mode, count)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        result = await fetch(start, end, mode) if kind == "route" else await fetch(start, end, mode, count)
        routes = [result] if kind == "route" else result
        self._cache.set(key, routes)
        return routes

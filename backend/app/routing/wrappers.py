"""
Provider-agnostic wrappers around any routing backend (an object with
get_route / get_alternative_routes): a fallback chain with a circuit breaker
and a result cache. Neither knows which provider is behind it, so swapping
providers stays a config change (ADR 0005).
"""
import asyncio
import logging
import time
from collections.abc import Callable

from app.cache import TTLCache
from app.routing.base import RoutingProviderError, RoutingQuotaError
from app.schemas import LonLat, RouteResult, TravelMode

log = logging.getLogger(__name__)


class FallbackRouting:
    """Try `primary`; on RoutingProviderError (network, quota, no route) try `fallback`.

    Circuit breaker: after a quota refusal (RoutingQuotaError) or
    `failure_threshold` failures in a row, `primary` is skipped for
    `cooldown_s`, so a dead or exhausted provider costs no latency per search.
    After the cooldown one request probes it again.
    """

    def __init__(
        self,
        primary,
        fallback,
        cooldown_s: float = 300.0,
        failure_threshold: int = 3,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._primary = primary
        self._fallback = fallback
        self._cooldown_s = cooldown_s
        self._failure_threshold = failure_threshold
        self._clock = clock
        self._failures = 0
        self._skip_until = 0.0

    def _primary_available(self) -> bool:
        return self._clock() >= self._skip_until

    def _record_failure(self, exc: RoutingProviderError) -> None:
        self._failures += 1
        if isinstance(exc, RoutingQuotaError) or self._failures >= self._failure_threshold:
            self._skip_until = self._clock() + self._cooldown_s
            self._failures = 0
            log.warning("primary routing disabled for %.0fs (%s)", self._cooldown_s, exc)

    async def _call(self, name: str, *args):
        if self._primary_available():
            try:
                result = await getattr(self._primary, name)(*args)
            except RoutingProviderError as exc:
                log.warning("primary routing failed (%s); using fallback", exc)
                self._record_failure(exc)
            else:
                self._failures = 0
                return result
        return await getattr(self._fallback, name)(*args)

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        return await self._call("get_route", start, end, mode)

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._call("get_alternative_routes", start, end, mode, count)


def _point(p: LonLat) -> tuple[float, float]:
    # 5 decimals is ~1 m: GPS jitter and re-clicks hit the same entry.
    return round(p.lon, 5), round(p.lat, 5)


def _copy(routes: list[RouteResult]) -> list[RouteResult]:
    return [r.model_copy(deep=True) for r in routes]


class CachedRouting:
    """Remembers successful routes. Failures are never cached.

    Wrap a single provider, not a fallback chain: caching above a
    FallbackRouting would pin degraded fallback answers for the full TTL.
    Concurrent identical requests share one upstream call. A single route is
    one cache entry whether asked for via get_route or
    get_alternative_routes(count=1). Callers always get copies, so mutating a
    result never corrupts the cache.
    """

    def __init__(self, inner, ttl_s: float = 3600.0, max_entries: int = 500):
        self._inner = inner
        self._cache: TTLCache[list[RouteResult]] = TTLCache(ttl_s, max_entries)
        self._in_flight: dict[tuple, asyncio.Future] = {}

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        return (await self._cached(start, end, mode, 1))[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._cached(start, end, mode, count)

    async def _fetch(self, start, end, mode, count) -> list[RouteResult]:
        if count == 1:
            return [await self._inner.get_route(start, end, mode)]
        return await self._inner.get_alternative_routes(start, end, mode, count)

    async def _cached(self, start, end, mode, count) -> list[RouteResult]:
        key = (_point(start), _point(end), mode, count)
        hit = self._cache.get(key)
        if hit is not None:
            return _copy(hit)

        task = self._in_flight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._fetch(start, end, mode, count))
            self._in_flight[key] = task

            def done(t: asyncio.Future) -> None:
                self._in_flight.pop(key, None)
                if not t.cancelled() and t.exception() is None:
                    self._cache.set(key, t.result())

            task.add_done_callback(done)
        # shield: one caller giving up must not cancel the call the others wait on.
        return _copy(await asyncio.shield(task))

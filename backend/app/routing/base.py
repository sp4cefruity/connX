"""
RoutingProvider — the abstraction the rest of the app codes against.

Nothing outside this package should import OSRM/Mapbox/Google-specific
code directly. Swapping providers means writing one new class here and
flipping the ROUTING_PROVIDER env var (see app/routing/__init__.py).
"""
from abc import ABC, abstractmethod

from app.schemas import GeocodeResult, LonLat, RouteResult, TravelMode


class RoutingProviderError(RuntimeError):
    """Raised when a provider fails (network, no route found, rate limit)."""


class RoutingQuotaError(RoutingProviderError):
    """The provider refused us for quota / auth reasons (HTTP 401, 403, 429).

    Retrying right away will not help, so FallbackRouting stops asking the
    provider for a while."""


class RoutingProvider(ABC):
    @abstractmethod
    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        ...

    @abstractmethod
    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        ...

    @abstractmethod
    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        ...

    @abstractmethod
    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        ...

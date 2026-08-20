from functools import lru_cache

from app.config import get_settings
from app.routing.base import RoutingProvider
from app.routing.mock import MockGeocoding, MockRouting
from app.routing.nominatim import NominatimGeocoding
from app.routing.osrm import OSRMRouting
from app.schemas import GeocodeResult, LonLat, RouteResult, TravelMode


class CompositeProvider(RoutingProvider):
    """Wires a routing backend + a geocoding backend into one RoutingProvider."""

    def __init__(self, routing, geocoding):
        self._routing = routing
        self._geocoding = geocoding

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        return await self._routing.get_route(start, end, mode)

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._routing.get_alternative_routes(start, end, mode, count)

    async def geocode(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        return await self._geocoding.geocode(query, limit)

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        return await self._geocoding.reverse_geocode(lon, lat)


@lru_cache
def get_routing_provider() -> RoutingProvider:
    settings = get_settings()

    if settings.routing_provider == "mock":
        routing = MockRouting()
    else:
        routing = OSRMRouting(settings.osrm_base_url)

    if settings.geocoding_provider == "mock":
        geocoding = MockGeocoding()
    else:
        geocoding = NominatimGeocoding(settings.nominatim_base_url, settings.nominatim_user_agent)

    return CompositeProvider(routing, geocoding)

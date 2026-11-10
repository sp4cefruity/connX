import logging
from functools import lru_cache

from app.config import get_settings
from app.routing.base import RoutingProvider
from app.routing.mock import MockGeocoding, MockRouting
from app.routing.nominatim import NominatimGeocoding
from app.routing.ors import ORSRouting
from app.routing.osrm import OSRMRouting
from app.routing.photon import FallbackGeocoding, PhotonGeocoding
from app.routing.wrappers import CachedRouting, FallbackRouting
from app.schemas import GeocodeResult, LonLat, RouteResult, TravelMode

log = logging.getLogger(__name__)


class CompositeProvider(RoutingProvider):
    """Wires a routing backend + a geocoding backend into one RoutingProvider."""

    def __init__(self, routing, geocoding):
        self._routing = routing
        self._geocoding = geocoding

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        return await self._routing.get_route(start, end, mode)

    async def get_route_via(self, start: LonLat, via: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        return await self._routing.get_route_via(start, via, end, mode)

    async def get_route_avoiding(
        self, start: LonLat, end: LonLat, mode: TravelMode, avoid: dict
    ) -> RouteResult:
        return await self._routing.get_route_avoiding(start, end, mode, avoid)

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._routing.get_alternative_routes(start, end, mode, count)

    async def geocode(
        self, query: str, limit: int = 5, lat: float | None = None, lon: float | None = None
    ) -> list[GeocodeResult]:
        return await self._geocoding.geocode(query, limit, lat=lat, lon=lon)

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        return await self._geocoding.reverse_geocode(lon, lat)


@lru_cache
def get_routing_provider() -> RoutingProvider:
    settings = get_settings()

    if settings.routing_provider == "mock":
        routing = MockRouting()
    else:
        routing = OSRMRouting(
            {
                "driving": settings.osrm_driving_base_url,
                "walking": settings.osrm_walking_base_url,
                "cycling": settings.osrm_cycling_base_url,
            }
        )
        # Cache each provider separately: a cache above the fallback chain would
        # keep serving degraded OSRM answers after ORS recovers (ADR 0005).
        routing = CachedRouting(
            routing, settings.route_cache_ttl_s, settings.route_cache_max_entries
        )
        if settings.routing_provider == "ors":
            if settings.ors_api_key:
                # ORS first, OSRM when ORS errors or its free quota runs out (ADR 0005).
                ors = CachedRouting(
                    ORSRouting(settings.ors_api_key, settings.ors_base_url),
                    settings.route_cache_ttl_s,
                    settings.route_cache_max_entries,
                )
                routing = FallbackRouting(ors, routing)
            else:
                log.warning("ROUTING_PROVIDER=ors but ORS_API_KEY is empty; using OSRM only")

    if settings.geocoding_provider == "mock":
        geocoding = MockGeocoding()
    else:
        geocoding = NominatimGeocoding(settings.nominatim_base_url, settings.nominatim_user_agent)
        if settings.geocoding_provider == "photon":
            # Photon for forward search, Nominatim fallback + reverse (ADR 0003).
            geocoding = FallbackGeocoding(
                PhotonGeocoding(
                    settings.photon_base_url,
                    settings.photon_timeout_s,
                    settings.nominatim_user_agent,
                ),
                geocoding,
            )

    return CompositeProvider(routing, geocoding)

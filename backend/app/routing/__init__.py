import logging
from functools import lru_cache

from app.config import get_settings
from app.routing.base import RoutingProvider
from app.routing.locationiq import LocationIQGeocoding
from app.routing.mock import MockGeocoding, MockRouting
from app.routing.nominatim import NominatimGeocoding
from app.routing.ors import ORSRouting
from app.routing.osrm import OSRMRouting
from app.routing.photon import FallbackGeocoding, PhotonGeocoding
# Valhalla is parked (ADR 0007): re-enable together with the branch below.
# from app.routing.valhalla import ValhallaRouting
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
        # Parked (ADR 0007): self-hosted Valhalla first, public OSRM as fallback.
        # if settings.routing_provider == "valhalla":
        #     valhalla = CachedRouting(
        #         ValhallaRouting(settings.valhalla_base_url),
        #         settings.route_cache_ttl_s,
        #         settings.route_cache_max_entries,
        #     )
        #     routing = FallbackRouting(valhalla, routing)
        # elif settings.routing_provider == "ors":
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
        geocoding = NominatimGeocoding(
            settings.nominatim_base_url,
            settings.nominatim_user_agent,
            # OSM's policy caps public use at 1 request/second.
            min_interval_s=0.0 if settings.environment == "development" else 1.0,
        )
        if settings.geocoding_provider == "photon":
            # Photon first, then LocationIQ (if keyed), then Nominatim, which also
            # does reverse geocoding (ADR 0003).
            chain = geocoding
            if settings.locationiq_api_key:
                chain = FallbackGeocoding(
                    LocationIQGeocoding(settings.locationiq_api_key, settings.locationiq_base_url),
                    geocoding,
                )
            else:
                log.warning("LOCATIONIQ_API_KEY is empty; search goes Photon -> Nominatim")
            geocoding = FallbackGeocoding(
                PhotonGeocoding(
                    settings.photon_base_url,
                    settings.photon_timeout_s,
                    settings.nominatim_user_agent,
                ),
                chain,
            )

    return CompositeProvider(routing, geocoding)

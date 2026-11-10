"""
Routing via OSRM (Open Source Routing Machine), one server per travel mode.

OSRM ignores the profile segment in the URL path: a server is built with a
single profile (car, foot or bike) and answers every /route/v1/<anything>/...
request with that profile. The public demo (router.project-osrm.org) is
car-only, so asking it for "foot" or "bike" silently returns the driving
route. To get correct routes per mode we therefore point each mode at its
own server (see docs/adr/0002-per-mode-osm-routing-servers.md). The OSM
German servers (routing.openstreetmap.de/routed-car|foot|bike) are the
defaults; the path profile is always "driving" because the server, not the
URL, decides the profile. For production, point the per-mode settings at
self-hosted OSRM instances.
"""
import httpx

from app.routing.base import RoutingProviderError
from app.schemas import LonLat, RouteResult, TravelMode

# The URL profile is cosmetic (the server's own profile wins); "driving" is
# the value every OSRM build accepts.
_URL_PROFILE = "driving"


class OSRMRouting:
    def __init__(
        self,
        base_urls: dict[TravelMode, str],
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_urls = {mode: url.rstrip("/") for mode, url in base_urls.items()}
        self._transport = transport

    def _base_url(self, mode: TravelMode) -> str:
        try:
            return self.base_urls[mode]
        except KeyError:
            raise RoutingProviderError(f"No routing server configured for mode '{mode}'") from None

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self.get_alternative_routes(start, end, mode, count=1)
        if not routes:
            raise RoutingProviderError("No route found")
        return routes[0]

    async def get_route_via(self, start: LonLat, via: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self._routes([start, via, end], mode, count=1)
        return routes[0]

    async def get_route_avoiding(
        self, start: LonLat, end: LonLat, mode: TravelMode, avoid: dict
    ) -> RouteResult:
        raise RoutingProviderError("OSRM cannot route around an area")

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._routes([start, end], mode, count)

    async def _routes(self, points: list[LonLat], mode: TravelMode, count: int) -> list[RouteResult]:
        coords = ";".join(f"{p.lon},{p.lat}" for p in points)
        url = f"{self._base_url(mode)}/route/v1/{_URL_PROFILE}/{coords}"
        params = {
            "alternatives": "true" if count > 1 else "false",
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
        }

        async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise RoutingProviderError(f"OSRM request failed: {exc}") from exc

        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise RoutingProviderError(f"OSRM returned no route: {data.get('code')}")

        results: list[RouteResult] = []
        for raw in data["routes"][:count]:
            coordinates = raw["geometry"]["coordinates"]  # [[lon, lat], ...]
            results.append(
                RouteResult(
                    distance_km=round(raw["distance"] / 1000, 2),
                    duration_min=round(raw["duration"] / 60, 1),
                    geometry=[LonLat(lon=c[0], lat=c[1]) for c in coordinates],
                    mode=mode,
                )
            )
        return results

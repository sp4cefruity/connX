"""
Routing via OSRM (Open Source Routing Machine).

Uses the free public demo server by default (router.project-osrm.org),
which is fine for development but is rate-limited and explicitly not
licensed for production traffic — see https://project-osrm.org/. For
production, point OSRM_BASE_URL at a self-hosted OSRM instance or swap
this module out for a commercial provider (Mapbox/Google/GraphHopper)
behind the same RoutingProvider interface.
"""
import httpx

from app.routing.base import RoutingProviderError
from app.schemas import LonLat, RouteResult, TravelMode

_PROFILE_MAP: dict[TravelMode, str] = {
    "driving": "driving",
    "walking": "foot",
    "cycling": "bike",
}


class OSRMRouting:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _profile(self, mode: TravelMode) -> str:
        return _PROFILE_MAP.get(mode, "driving")

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self.get_alternative_routes(start, end, mode, count=1)
        if not routes:
            raise RoutingProviderError("No route found")
        return routes[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        profile = self._profile(mode)
        coords = f"{start.lon},{start.lat};{end.lon},{end.lat}"
        url = f"{self.base_url}/route/v1/{profile}/{coords}"
        params = {
            "alternatives": "true" if count > 1 else "false",
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
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

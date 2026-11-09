"""
Routing via OpenRouteService (ORS), hosted free tier.

One endpoint serves every mode; the mode picks the ORS profile. The key goes in
the Authorization header. Free-tier directions quota is 2,000/day and 40/min
(https://openrouteservice.org/plans/), so ORS is always wrapped by a result
cache and a fallback to OSRM (ADR 0005).

Alternative routes are capped by ORS at 3 routes and ~100 km. When the
request is refused for being too long, we retry for the single best route
rather than failing the whole search.
"""
import httpx

from app.routing.base import RoutingProviderError
from app.schemas import LonLat, RouteResult, TravelMode

_PROFILES: dict[str, str] = {
    "driving": "driving-car",
    "walking": "foot-walking",
    "cycling": "cycling-regular",
}
_MAX_ALTERNATIVES = 3  # public ORS cap


class ORSRouting:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openrouteservice.org",
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._transport = transport

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self.get_alternative_routes(start, end, mode, count=1)
        if not routes:
            raise RoutingProviderError("No route found")
        return routes[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        profile = _PROFILES.get(mode)
        if profile is None:
            raise RoutingProviderError(f"ORS has no profile for mode '{mode}'")

        body: dict = {"coordinates": [[start.lon, start.lat], [end.lon, end.lat]]}
        if count > 1:
            body["alternative_routes"] = {
                "target_count": min(count, _MAX_ALTERNATIVES),
                "share_factor": 0.6,
                "weight_factor": 1.6,
            }

        resp = await self._post(profile, body)
        if resp.status_code == 400 and count > 1:
            # Over the alternatives distance cap (or no alternatives exist).
            resp = await self._post(profile, {"coordinates": body["coordinates"]})

        if resp.status_code != 200:
            raise RoutingProviderError(f"ORS returned HTTP {resp.status_code}")

        try:
            features = resp.json()["features"]
            results = [
                RouteResult(
                    distance_km=round(f["properties"]["summary"]["distance"] / 1000, 2),
                    duration_min=round(f["properties"]["summary"]["duration"] / 60, 1),
                    geometry=[LonLat(lon=c[0], lat=c[1]) for c in f["geometry"]["coordinates"]],
                    mode=mode,
                )
                for f in features
            ]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RoutingProviderError(f"ORS returned an unreadable response: {exc}") from exc

        if not results:
            raise RoutingProviderError("ORS returned no route")
        return results[:count]

    async def _post(self, profile: str, body: dict) -> httpx.Response:
        url = f"{self.base_url}/v2/directions/{profile}/geojson"
        async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
            try:
                return await client.post(url, json=body, headers={"Authorization": self.api_key})
            except httpx.HTTPError as exc:
                raise RoutingProviderError(f"ORS request failed: {exc}") from exc

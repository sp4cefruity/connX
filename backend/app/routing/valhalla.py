"""
Routing via a self-hosted Valhalla server (ADR 0007).

One /route endpoint serves every mode; the mode picks the costing model
(auto, pedestrian, bicycle). Unlike OSRM, Valhalla can keep a route out of
areas (`exclude_polygons`) and return alternatives, so Recommend can find real
detours. Self-hosting means no quota and no rate limit; the cost is that tiles
only cover the extract they were built from, so a point outside it is an
ordinary RoutingProviderError and FallbackRouting retries on public OSRM.
"""
import httpx

from app.routing.base import RoutingProviderError, RoutingRejectedError, RoutingUnavailableError
from app.schemas import LonLat, RouteResult, TravelMode

_COSTING: dict[str, str] = {
    "driving": "auto",
    "walking": "pedestrian",
    "cycling": "bicycle",
}


def decode_polyline6(encoded: str) -> list[LonLat]:
    """Decode Valhalla's encoded shape (polyline, 6 decimal digits) to lon/lat points."""
    points: list[LonLat] = []
    index = lat = lon = 0
    n = len(encoded)
    while index < n:
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= n:
                    raise ValueError("truncated polyline")
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append(LonLat(lon=lon / 1e6, lat=lat / 1e6))
    return points


def _rings(area: dict) -> list[list[list[float]]]:
    """Outer rings of a GeoJSON Polygon / MultiPolygon, as Valhalla's exclude_polygons.

    Valhalla's exclude_polygons takes plain rings, with no way to express a
    hole, so holes are dropped (the hole's area stays excluded)."""
    kind = area.get("type")
    coords = area.get("coordinates")
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        raise RoutingProviderError(f"Cannot avoid a '{kind}' area")
    try:
        return [[[c[0], c[1]] for c in poly[0]] for poly in polygons]
    except (TypeError, IndexError, KeyError) as exc:
        raise RoutingProviderError(f"Unreadable avoid area: {exc}") from exc


class ValhallaRouting:
    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._transport = transport

    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self._routes([start, end], mode, count=1)
        return routes[0]

    async def get_route_via(self, start: LonLat, via: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self._routes([start, via, end], mode, count=1)
        return routes[0]

    async def get_route_avoiding(
        self, start: LonLat, end: LonLat, mode: TravelMode, avoid: dict
    ) -> RouteResult:
        """The best route that keeps out of `avoid`, a GeoJSON (Multi)Polygon.

        Valhalla caps the total perimeter of exclude polygons
        (service_limits.max_exclude_polygons_length); see ADR 0007.
        """
        routes = await self._routes([start, end], mode, count=1, avoid=avoid)
        return routes[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        return await self._routes([start, end], mode, count)

    async def _routes(
        self, points: list[LonLat], mode: TravelMode, count: int, avoid: dict | None = None
    ) -> list[RouteResult]:
        costing = _COSTING.get(mode)
        if costing is None:
            raise RoutingProviderError(f"Valhalla has no costing for mode '{mode}'")

        locations = [{"lat": p.lat, "lon": p.lon, "type": "break"} for p in points]
        # Pass through via points instead of stopping (and turning round) at them.
        for loc in locations[1:-1]:
            loc["type"] = "through"
        body: dict = {"locations": locations, "costing": costing, "directions_type": "none"}
        if avoid is not None:
            body["exclude_polygons"] = _rings(avoid)
        if count > 1 and len(points) == 2:
            body["alternates"] = count - 1

        url = f"{self.base_url}/route"
        async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
            try:
                resp = await client.post(url, json=body)
            except httpx.HTTPError as exc:
                raise RoutingUnavailableError(f"Valhalla request failed: {exc}") from exc

        if resp.status_code != 200:
            message = f"Valhalla returned HTTP {resp.status_code}: {self._message(resp)}"
            if 400 <= resp.status_code < 500:
                # Point outside the tiles, no path, or an exclude area over the
                # server's size limit: this request only, not an outage.
                raise RoutingRejectedError(message)
            raise RoutingUnavailableError(message)

        try:
            data = resp.json()
            trips = [data["trip"]] + [a["trip"] for a in data.get("alternates") or []]
            results = [self._result(t, mode) for t in trips]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RoutingProviderError(f"Valhalla returned an unreadable response: {exc}") from exc
        if not results:
            raise RoutingProviderError("Valhalla returned no route")
        return results[:count]

    @staticmethod
    def _result(trip: dict, mode: TravelMode) -> RouteResult:
        geometry: list[LonLat] = []
        for leg in trip["legs"]:
            shape = decode_polyline6(leg["shape"])
            # Consecutive legs share their joining point.
            geometry.extend(shape[1:] if geometry else shape)
        if not geometry:
            raise ValueError("empty shape")
        summary = trip["summary"]
        return RouteResult(
            distance_km=round(summary["length"], 2),  # Valhalla's default unit is km
            duration_min=round(summary["time"] / 60, 1),
            geometry=geometry,
            mode=mode,
        )

    @staticmethod
    def _message(resp: httpx.Response) -> str:
        try:
            data = resp.json()
            return f"{data.get('error_code')} {data.get('error')}"
        except (ValueError, AttributeError):
            return "no detail"

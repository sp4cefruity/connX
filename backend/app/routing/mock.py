"""
Offline mock provider. No network calls — used for unit tests and local
frontend work when you don't want to depend on the public OSRM/Nominatim
demo servers. Generates a slightly wiggly straight-line route so overlap
math has something non-trivial to chew on.
"""
import math

from app.schemas import GeocodeResult, LonLat, RouteResult, TravelMode

_AVG_SPEED_KMH: dict[TravelMode, float] = {"driving": 35.0, "walking": 5.0, "cycling": 15.0}


def _haversine_km(a: LonLat, b: LonLat) -> float:
    r = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _wiggly_line(start: LonLat, end: LonLat, seed: float, n: int = 12) -> list[LonLat]:
    pts = []
    for i in range(n + 1):
        t = i / n
        lon = start.lon + (end.lon - start.lon) * t
        lat = start.lat + (end.lat - start.lat) * t
        wiggle = math.sin(t * math.pi * 3 + seed) * 0.0015 * math.sin(t * math.pi)
        pts.append(LonLat(lon=lon + wiggle, lat=lat + wiggle * 0.6))
    return pts


class MockRouting:
    async def get_route(self, start: LonLat, end: LonLat, mode: TravelMode) -> RouteResult:
        routes = await self.get_alternative_routes(start, end, mode, count=1)
        return routes[0]

    async def get_alternative_routes(
        self, start: LonLat, end: LonLat, mode: TravelMode, count: int = 3
    ) -> list[RouteResult]:
        base_km = _haversine_km(start, end)
        speed = _AVG_SPEED_KMH.get(mode, 35.0)
        results = []
        for i in range(count):
            seed = i * 1.7
            geometry = _wiggly_line(start, end, seed)
            distance_km = round(base_km * (1 + i * 0.08), 2)
            duration_min = round(distance_km / speed * 60, 1)
            results.append(RouteResult(distance_km=distance_km, duration_min=duration_min, geometry=geometry, mode=mode))
        return results


class MockGeocoding:
    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        # Deterministic fake coordinates around Bhubaneswar so the demo is stable.
        base_lat, base_lon = 20.2961, 85.8245
        h = sum(ord(c) for c in query) % 100
        return [
            GeocodeResult(
                label=query,
                address=f"{query}, Bhubaneswar, Odisha (mock)",
                lon=base_lon + (h - 50) * 0.001,
                lat=base_lat + (h - 50) * 0.0007,
            )
        ][:limit]

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        return GeocodeResult(label="Mock location", address="Mock location", lon=lon, lat=lat)

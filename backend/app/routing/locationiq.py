"""
Forward geocoding via LocationIQ's autocomplete endpoint (second in the chain:
Photon -> LocationIQ -> Nominatim).

Free tier is roughly 5,000 requests a day and 2 per second, so unlike the
Photon and Nominatim providers this makes ONE request per search: a box of about
+/-1000 km around the user, sorted nearest-first on our side. If that box is
empty it retries worldwide. Needs LOCATIONIQ_API_KEY; get_routing_provider only
adds it to the chain when a key is set.
"""
import httpx

from app.routing.base import RoutingProviderError
from app.routing.photon import _RING_HALF_SPANS_DEG, _place_key, _rank_key
from app.schemas import GeocodeResult

_MIN_POOL = 10


class LocationIQGeocoding:
    def __init__(self, api_key: str, base_url: str = "https://us1.locationiq.com", timeout_s: float = 4.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        pool = max(limit, _MIN_POOL)
        if lat is None or lon is None:
            return (await self._search(query, pool))[:limit]

        d = _RING_HALF_SPANS_DEG[-1]
        # LocationIQ viewbox: lon1,lat1,lon2,lat2 (opposite corners).
        box = f"{lon - d:.4f},{lat + d:.4f},{lon + d:.4f},{lat - d:.4f}"
        found = await self._search(query, pool, box)
        if not found:
            return (await self._search(query, pool))[:limit]

        unique: list[GeocodeResult] = []
        seen: set[tuple[str, str]] = set()
        for r in found:
            key = _place_key(r)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=_rank_key(query, lat, lon))
        return unique[:limit]

    async def _search(self, query: str, limit: int, viewbox: str | None = None) -> list[GeocodeResult]:
        params: dict[str, str | int] = {"key": self.api_key, "q": query, "limit": limit, "format": "json"}
        if viewbox is not None:
            params["viewbox"] = viewbox
            params["bounded"] = 1
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                resp = await client.get(f"{self.base_url}/v1/autocomplete", params=params)
                if resp.status_code == 404:  # LocationIQ answers 404 for "no matches"
                    return []
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RoutingProviderError(f"LocationIQ request failed: {type(exc).__name__}") from exc

        results: list[GeocodeResult] = []
        for item in data if isinstance(data, list) else []:
            try:
                label = item.get("display_place") or (item.get("display_name") or "").split(",")[0]
                if not label:
                    continue
                results.append(
                    GeocodeResult(
                        label=label,
                        address=item.get("display_name"),
                        lon=float(item["lon"]),
                        lat=float(item["lat"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return results

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        raise NotImplementedError("Reverse geocoding stays on Nominatim")

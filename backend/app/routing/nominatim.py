"""
Geocoding via Nominatim (OpenStreetMap's free geocoder).

Nominatim's usage policy requires a descriptive User-Agent and caps
usage at ~1 request/second — see NOMINATIM_USER_AGENT in config and the
in-memory cache in app/routers/geocode.py. For higher volume, self-host
Nominatim or switch to a commercial geocoder behind this same interface.
"""
import httpx

from app.routing.base import RoutingProviderError
from app.schemas import GeocodeResult


class NominatimGeocoding:
    def __init__(self, base_url: str, user_agent: str):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        # lat/lon bias is accepted for interface parity with Photon but unused here.
        url = f"{self.base_url}/search"
        params = {"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 0}
        headers = {"User-Agent": self.user_agent}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise RoutingProviderError(f"Nominatim request failed: {exc}") from exc

        return [
            GeocodeResult(
                label=item.get("name") or item.get("display_name", "").split(",")[0],
                address=item.get("display_name"),
                lon=float(item["lon"]),
                lat=float(item["lat"]),
            )
            for item in resp.json()
        ]

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        url = f"{self.base_url}/reverse"
        params = {"lon": lon, "lat": lat, "format": "jsonv2"}
        headers = {"User-Agent": self.user_agent}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise RoutingProviderError(f"Nominatim request failed: {exc}") from exc

        data = resp.json()
        if "error" in data:
            return None
        return GeocodeResult(
            label=data.get("name") or data.get("display_name", "").split(",")[0],
            address=data.get("display_name"),
            lon=float(data["lon"]),
            lat=float(data["lat"]),
        )

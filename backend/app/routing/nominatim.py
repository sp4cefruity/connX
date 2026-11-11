"""
Geocoding via Nominatim (OpenStreetMap's free geocoder).

Nominatim's usage policy requires a descriptive User-Agent and caps
usage at ~1 request/second — see NOMINATIM_USER_AGENT in config and the
in-memory cache in app/routers/geocode.py. Requests go out one at a time,
and `min_interval_s` (1 s in production) spaces them to honour that cap. For
higher volume, self-host Nominatim or switch to a commercial geocoder behind
this same interface.
"""
import asyncio
import time

import httpx

from app.routing.base import RoutingProviderError
from app.routing.photon import _RING_HALF_SPANS_DEG, _rank_key
from app.schemas import GeocodeResult


def _viewbox(lat: float, lon: float, d: float) -> str:
    # Nominatim wants left,top,right,bottom.
    return f"{lon - d:.4f},{lat + d:.4f},{lon + d:.4f},{lat - d:.4f}"


class NominatimGeocoding:
    def __init__(self, base_url: str, user_agent: str, min_interval_s: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def _get(self, url: str, params: dict) -> httpx.Response:
        """One request at a time, at least `min_interval_s` apart."""
        async with self._lock:
            wait = self._last_request + self.min_interval_s - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params=params, headers={"User-Agent": self.user_agent})
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as exc:
                raise RoutingProviderError(f"Nominatim request failed: {exc}") from exc
            finally:
                self._last_request = time.monotonic()

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        if lat is None or lon is None:
            return await self._search(query, limit)

        # Same idea as Photon: boxes of growing size around the user, merged and
        # sorted nearest first; worldwide only if every box is empty. Asked in
        # turn, never in parallel (usage policy).
        outcomes: list[list[GeocodeResult] | BaseException] = []
        for d in _RING_HALF_SPANS_DEG:
            try:
                outcomes.append(await self._search(query, max(limit, 10), _viewbox(lat, lon, d)))
            except Exception as exc:  # one failed box must not sink the others
                outcomes.append(exc)
        if all(isinstance(o, BaseException) for o in outcomes):
            raise outcomes[0]
        found = [r for o in outcomes if not isinstance(o, BaseException) for r in o]
        if not found:
            return await self._search(query, limit)

        unique: list[GeocodeResult] = []
        seen: set[tuple[str, str]] = set()
        for r in found:
            key = (r.label.lower(), (r.address or "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=_rank_key(query, lat, lon))
        return unique[:limit]

    async def _search(self, query: str, limit: int, viewbox: str | None = None) -> list[GeocodeResult]:
        url = f"{self.base_url}/search"
        params: dict[str, str | int] = {"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 0}
        if viewbox is not None:
            params["viewbox"] = viewbox
            params["bounded"] = 1
        resp = await self._get(url, params)

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
        resp = await self._get(url, params)

        data = resp.json()
        if "error" in data:
            return None
        return GeocodeResult(
            label=data.get("name") or data.get("display_name", "").split(",")[0],
            address=data.get("display_name"),
            lon=float(data["lon"]),
            lat=float(data["lat"]),
        )

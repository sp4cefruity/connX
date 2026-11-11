"""
Forward geocoding via Photon (komoot's OSM-backed, type-ahead friendly geocoder).

Response format (verified against https://photon.komoot.io/api/): a GeoJSON
FeatureCollection. Each feature has `geometry.coordinates` = [lon, lat] and
`properties` with `name`, `street`, `housenumber`, `district`, `city`,
`state`, `country`, ... (any may be missing). Viewport bias is the plain
`lat` + `lon` query params; Photon ranks nearby results higher but does not
exclude far ones.

Photon's public server is fair-use with no SLA, so it is wrapped by
FallbackGeocoding (below) which drops to Nominatim on timeout/error
(ADR 0003). Photon has no reverse endpoint we rely on: reverse stays on
Nominatim.
"""
import asyncio
import math
import time

import httpx

from app.routing.base import RoutingProviderError
from app.schemas import GeocodeResult

# Photon's lat/lon bias is soft: it happily returns a same-named place on
# another continent. So when we know where the user is, we search boxes of
# growing size around them (about 55 km, 330 km, 1000 km) in parallel, merge
# the hits, and sort strictly by distance from the user. A worldwide search is
# a last resort, used only when no box has anything.
_RING_HALF_SPANS_DEG = (0.5, 3.0, 9.0)
_MAX_TRIMMED_WORDS = 2
_MIN_POOL = 10  # fetch more than we show so distance sorting has something to sort
_EARTH_RADIUS_KM = 6371.0


def _bbox(lat: float, lon: float, half_span_deg: float) -> str:
    d = half_span_deg
    return f"{lon - d:.4f},{lat - d:.4f},{lon + d:.4f},{lat + d:.4f}"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def _rank_key(query: str, lat: float, lon: float):
    """Nearer ring first; inside a ring, names starting with the query, then nearest."""
    q = query.strip().lower()

    def key(r: GeocodeResult):
        d = _distance_km(lat, lon, r.lat, r.lon)
        ring = next((i for i, span in enumerate(_RING_HALF_SPANS_DEG) if d <= span * 111), len(_RING_HALF_SPANS_DEG))
        return (ring, not r.label.lower().startswith(q), d)

    return key


def _place_key(r: GeocodeResult) -> tuple[str, str]:
    # Two rows that read identically in the dropdown are one result to the user.
    return (r.label.lower(), (r.address or "").lower())


class PhotonGeocoding:
    def __init__(
        self,
        base_url: str = "https://photon.komoot.io",
        timeout_s: float = 3.0,
        user_agent: str = "ConnX/0.1 (dev)",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        # photon.komoot.io rejects the default python-httpx User-Agent with a
        # 403, which silently sent every search to the Nominatim fallback.
        self.user_agent = user_agent

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        if lat is None or lon is None:
            return await self._search(query, limit)

        pool = max(limit, _MIN_POOL)
        outcomes = await asyncio.gather(
            *(self._search(query, pool, lat, lon, _bbox(lat, lon, d)) for d in _RING_HALF_SPANS_DEG),
            return_exceptions=True,
        )
        if all(isinstance(o, BaseException) for o in outcomes):
            raise outcomes[0]
        # One ring failing is not fatal; the others still answer.
        found = [r for o in outcomes if not isinstance(o, BaseException) for r in o]

        if not found:
            found = await self._search_trimmed(query, pool, lat, lon, _bbox(lat, lon, _RING_HALF_SPANS_DEG[1]))
        if not found:
            found = await self._search(query, pool, lat, lon)

        unique: list[GeocodeResult] = []
        seen: set[tuple[str, str]] = set()
        for r in found:
            key = _place_key(r)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=_rank_key(query, lat, lon))
        return unique[:limit]

    async def _search_trimmed(
        self, query: str, limit: int, lat: float, lon: float, bbox: str
    ) -> list[GeocodeResult]:
        words = query.split()
        for dropped in range(1, _MAX_TRIMMED_WORDS + 1):
            if len(words) - dropped < 1:
                break
            try:
                found = await self._search(" ".join(words[:-dropped]), limit, lat, lon, bbox)
            except RoutingProviderError:
                return []
            if found:
                return found
        return []

    async def _search(
        self,
        query: str,
        limit: int,
        lat: float | None = None,
        lon: float | None = None,
        bbox: str | None = None,
    ) -> list[GeocodeResult]:
        params: dict[str, str | int | float] = {"q": query, "limit": limit}
        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon
        if bbox is not None:
            params["bbox"] = bbox

        async with httpx.AsyncClient(
            timeout=self.timeout_s, headers={"User-Agent": self.user_agent}
        ) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/", params=params)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RoutingProviderError(f"Photon request failed: {exc}") from exc

        results: list[GeocodeResult] = []
        for feature in data.get("features", []):
            parsed = _parse_feature(feature)
            if parsed is not None:
                results.append(parsed)
        return results

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        raise NotImplementedError("Reverse geocoding stays on Nominatim (ADR 0003)")


def _parse_feature(feature: dict) -> GeocodeResult | None:
    try:
        lon, lat = feature["geometry"]["coordinates"][:2]
        props = feature.get("properties") or {}
        street = props.get("street")
        housenumber = props.get("housenumber")
        street_line = " ".join(p for p in (housenumber, street) if p) or None

        label = props.get("name") or street_line
        if not label:
            return None

        parts: list[str] = []
        for part in (
            props.get("name"),
            street_line,
            props.get("district"),
            props.get("city"),
            props.get("state"),
            props.get("country"),
        ):
            if part and part not in parts:
                parts.append(part)

        return GeocodeResult(label=label, address=", ".join(parts), lon=float(lon), lat=float(lat))
    except (KeyError, TypeError, ValueError):
        return None


class FallbackGeocoding:
    """Forward search tries `primary`; on provider error falls back to
    `fallback`. Reverse geocoding always uses `fallback`.

    After the primary fails it is skipped for `cooldown_s`, so a dead Photon
    costs one slow request, not a timeout on every keystroke.
    """

    def __init__(self, primary, fallback, cooldown_s: float = 60.0, clock=time.monotonic):
        self._primary = primary
        self._fallback = fallback
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._skip_until = 0.0

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        if self._clock() >= self._skip_until:
            try:
                return await self._primary.geocode(query, limit, lat=lat, lon=lon)
            except RoutingProviderError:
                self._skip_until = self._clock() + self._cooldown_s
        return await self._fallback.geocode(query, limit, lat=lat, lon=lon)

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        return await self._fallback.reverse_geocode(lon, lat)

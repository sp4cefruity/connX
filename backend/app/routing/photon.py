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

import httpx

from app.routing.base import RoutingProviderError
from app.schemas import GeocodeResult

# Photon's lat/lon bias is soft, and it needs every word of the query to match.
# So "esplanade one mall" (OSM only knows the place as "Esplanade") found
# nothing nearby and fell through to Manila and Gold Coast. When we know where
# the map is, we also search a box around it (about +/-55 km), and if that box
# has nothing we retry it with trailing words dropped.
_REGION_HALF_SPAN_DEG = 0.5
_MAX_TRIMMED_WORDS = 2
# Regional hits that only matched a shortened query: keep a couple, but leave
# room for worldwide matches of the full query (e.g. a user really after "new york").
_MAX_TRIMMED_RESULTS = 2


def _region_bbox(lat: float, lon: float) -> str:
    d = _REGION_HALF_SPAN_DEG
    return f"{lon - d:.4f},{lat - d:.4f},{lon + d:.4f},{lat + d:.4f}"


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

        bbox = _region_bbox(lat, lon)
        regional, worldwide = await asyncio.gather(
            self._search(query, limit, lat, lon, bbox),
            self._search(query, limit, lat, lon),
            return_exceptions=True,
        )
        if isinstance(regional, BaseException) and isinstance(worldwide, BaseException):
            raise regional
        # One side failing is not fatal; the other still answers.
        if isinstance(regional, BaseException):
            regional = []
        if isinstance(worldwide, BaseException):
            worldwide = []

        trimmed = False
        if not regional:
            regional = await self._search_trimmed(query, limit, lat, lon, bbox)
            trimmed = bool(regional)
        if trimmed:
            regional = regional[:_MAX_TRIMMED_RESULTS]

        merged: list[GeocodeResult] = []
        seen: set[tuple[str, str]] = set()
        for r in [*regional, *worldwide]:
            key = _place_key(r)
            if key not in seen:
                seen.add(key)
                merged.append(r)
        return merged[:limit]

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
    """Forward search tries `primary` (Photon); on provider error falls back to
    `fallback` (Nominatim). Reverse geocoding always uses `fallback`."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        try:
            return await self._primary.geocode(query, limit, lat=lat, lon=lon)
        except RoutingProviderError:
            # Nominatim ignores the bias; if it also fails the error propagates
            # and the endpoint reports "search is slow right now".
            return await self._fallback.geocode(query, limit, lat=lat, lon=lon)

    async def reverse_geocode(self, lon: float, lat: float) -> GeocodeResult | None:
        return await self._fallback.reverse_geocode(lon, lat)

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
import httpx

from app.routing.base import RoutingProviderError
from app.schemas import GeocodeResult


class PhotonGeocoding:
    def __init__(self, base_url: str = "https://photon.komoot.io", timeout_s: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[GeocodeResult]:
        params: dict[str, str | int | float] = {"q": query, "limit": limit}
        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
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

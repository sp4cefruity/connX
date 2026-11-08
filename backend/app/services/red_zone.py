"""
Red zone band (ADR 0001): the area within the danger distance of Route B.

Route B is projected into a local metric plane, buffered by the danger
distance there, and projected back to lon/lat. The result is a single GeoJSON
polygon so the map can fill it once (a translucent line layer would darken
wherever the stroke overlaps itself).

Pure Python/Shapely - no DB or network - unit tested in tests/test_red_zone.py.
"""
from shapely.geometry import LineString, mapping

from app.schemas import LonLat
from app.services.projection import Projection, mean_lat

# Drop vertices that move the band edge by less than this; keeps the payload
# small for long routes without visibly changing a 50 m+ band.
_SIMPLIFY_TOLERANCE_M = 2.0


def build_red_zone_band(route_b_geometry: list[LonLat], danger_distance_m: float) -> dict | None:
    """GeoJSON (Multi)Polygon geometry in lon/lat, or None if Route B has no length."""
    if len(route_b_geometry) < 2:
        return None

    proj = Projection(ref_lat=mean_lat(route_b_geometry))
    b_line = LineString(proj.to_xy(route_b_geometry))
    if b_line.length == 0:
        return None

    band = b_line.buffer(danger_distance_m).simplify(_SIMPLIFY_TOLERANCE_M, preserve_topology=True)

    geojson = mapping(band)
    polygons = [geojson["coordinates"]] if geojson["type"] == "Polygon" else geojson["coordinates"]
    out = [
        [[(round(p.lon, 6), round(p.lat, 6)) for p in proj.to_lonlat(ring)] for ring in polygon]
        for polygon in polygons
    ]
    if geojson["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": out[0]}
    return {"type": "MultiPolygon", "coordinates": out}

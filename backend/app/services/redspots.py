"""
Red spot detection (spec §12): does a route pass through a saved
avoidance zone? Uses the same equirectangular projection as overlap.py
so distances are in real metres.
"""
import math

from shapely.geometry import LineString, Point

from app.models import SavedLocation
from app.schemas import LonLat, RedSpot, RedSpotHit

_METERS_PER_DEG_LAT = 111_320.0


def _project_point(lon: float, lat: float, ref_lat: float) -> tuple[float, float]:
    cos_lat = math.cos(math.radians(ref_lat))
    return (lon * _METERS_PER_DEG_LAT * cos_lat, lat * _METERS_PER_DEG_LAT)


def find_red_spot_hits(
    route_geometry: list[LonLat], red_spots: list[SavedLocation]
) -> list[RedSpotHit]:
    if not route_geometry or not red_spots:
        return []

    ref_lat = sum(c.lat for c in route_geometry) / len(route_geometry)
    line = LineString([_project_point(c.lon, c.lat, ref_lat) for c in route_geometry])

    hits = []
    for spot in red_spots:
        point = Point(_project_point(spot.longitude, spot.latitude, ref_lat))
        distance_m = line.distance(point)
        hits.append(
            RedSpotHit(
                red_spot=RedSpot.model_validate(spot),
                intersects=distance_m <= spot.radius_m,
                min_distance_m=round(distance_m, 1),
            )
        )
    return hits

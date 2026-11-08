"""
Local metric projection shared by the spatial services.

A simple equirectangular projection around a reference latitude: good to
within ~0.1% at city scale, which is fine for tolerances and danger
distances of 25 m - 1 km. Production PostGIS deployments should do this with
ST_Transform into a local UTM SRID instead; see init.sql.
"""
import math
from dataclasses import dataclass

from app.schemas import LonLat

METERS_PER_DEG_LAT = 111_320.0


@dataclass
class Projection:
    ref_lat: float

    def to_xy(self, coords: list[LonLat]) -> list[tuple[float, float]]:
        cos_lat = math.cos(math.radians(self.ref_lat))
        return [
            (c.lon * METERS_PER_DEG_LAT * cos_lat, c.lat * METERS_PER_DEG_LAT)
            for c in coords
        ]

    def to_lonlat(self, coords) -> list[LonLat]:
        cos_lat = math.cos(math.radians(self.ref_lat))
        return [
            LonLat(lon=x / (METERS_PER_DEG_LAT * cos_lat), lat=y / METERS_PER_DEG_LAT)
            for x, y in coords
        ]


def mean_lat(*coord_lists: list[LonLat]) -> float:
    all_lats = [c.lat for coords in coord_lists for c in coords]
    return sum(all_lats) / len(all_lats)

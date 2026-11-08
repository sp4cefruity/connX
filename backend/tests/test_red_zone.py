"""Red zone band: Route B buffered by the danger distance, in metres."""
import math

from shapely.geometry import Point, shape

from app.schemas import LonLat
from app.services.red_zone import build_red_zone_band

M_PER_DEG_LAT = 111_320.0


def _line(coords):
    return [LonLat(lon=lon, lat=lat) for lon, lat in coords]


def _offset_north(lat: float, metres: float) -> float:
    return lat + metres / M_PER_DEG_LAT


# A ~2 km west->east road.
ROUTE_B = _line([(85.800, 20.290), (85.818, 20.290)])
MID_LON = 85.809


def test_band_contains_points_inside_danger_distance_and_excludes_outside():
    band = shape(build_red_zone_band(ROUTE_B, 200))
    assert band.contains(Point(MID_LON, _offset_north(20.290, 150)))
    assert not band.contains(Point(MID_LON, _offset_north(20.290, 250)))
    # Symmetric: the band surrounds the route, it is not one-sided.
    assert band.contains(Point(MID_LON, _offset_north(20.290, -150)))


def test_band_width_follows_danger_distance():
    narrow = shape(build_red_zone_band(ROUTE_B, 50))
    wide = shape(build_red_zone_band(ROUTE_B, 800))
    probe = Point(MID_LON, _offset_north(20.290, 400))
    assert not narrow.contains(probe)
    assert wide.contains(probe)


def test_band_half_width_is_in_metres_east_west_too():
    # The projection must correct for longitude shrinking with latitude:
    # past the route's end the band extends by the danger distance in metres.
    band = shape(build_red_zone_band(ROUTE_B, 200))
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(20.290))
    end_lon = ROUTE_B[-1].lon
    assert band.contains(Point(end_lon + 150 / m_per_deg_lon, 20.290))
    assert not band.contains(Point(end_lon + 250 / m_per_deg_lon, 20.290))


def test_band_is_a_geojson_polygon_in_lonlat():
    geom = build_red_zone_band(ROUTE_B, 200)
    assert geom["type"] in ("Polygon", "MultiPolygon")
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    lon, lat = ring[0][:2]
    assert 85.7 < lon < 85.9 and 20.2 < lat < 20.4  # degrees, not metres


def test_too_short_route_has_no_band():
    assert build_red_zone_band(_line([(85.8, 20.29)]), 200) is None
    assert build_red_zone_band([], 200) is None

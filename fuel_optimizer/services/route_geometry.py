"""WGS84 lengths and indexed, local great-circle projection; never degree distances."""

import math
from dataclasses import dataclass

from pyproj import Geod
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

from fuel_optimizer.errors import PlanningError

from .routing import METERS_PER_MILE

GEOD = Geod(ellps="WGS84")


def distance_miles(a, b):
    return GEOD.inv(a[0], a[1], b[0], b[1])[2] / METERS_PER_MILE


def _bearing(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    delta = lon2 - lon1
    return math.atan2(
        math.sin(delta) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta),
    )


def _angle(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


@dataclass(frozen=True)
class Projection:
    route_offset_miles: float
    distance_from_route_miles: float
    nearest_longitude: float
    nearest_latitude: float


class RouteGeometry:
    def __init__(self, coordinates, route_distance_miles):
        # Densify long segments to <=5 mi to bound spherical/ellipsoidal projection error.
        dense = [tuple(coordinates[0])]
        for end in coordinates[1:]:
            start = dense[-1]
            length = distance_miles(start, end)
            if length < 1e-9:
                continue
            count = max(0, math.ceil(length / 5) - 1)
            if count:
                dense.extend(GEOD.npts(*start, *end, count))
            dense.append(tuple(end))
        if len(dense) < 2:
            raise PlanningError("osrm_invalid_response", "Route geometry has zero length.", 502)
        # Unwrap longitudes for Alaska/dateline spatial indexing.
        self.points = [dense[0]]
        for longitude, latitude in dense[1:]:
            previous = self.points[-1][0]
            longitude += 360 * round((previous - longitude) / 360)
            self.points.append((longitude, latitude))
        self.cumulative_miles = [0.0]
        self.lengths = []
        self.azimuths = []
        for a, b in zip(self.points, self.points[1:]):
            azimuth, _, meters = GEOD.inv(*a, *b)
            length = meters / METERS_PER_MILE
            self.lengths.append(length)
            self.azimuths.append(azimuth)
            self.cumulative_miles.append(self.cumulative_miles[-1] + length)
        self.scale = route_distance_miles / self.cumulative_miles[-1]
        if not 0.5 <= self.scale <= 2:
            raise PlanningError("osrm_invalid_response", "Route distance is inconsistent with geometry.", 502)
        self.tree = STRtree([LineString([a, b]) for a, b in zip(self.points, self.points[1:])])
        self.longitude_reference = sum(p[0] for p in self.points) / len(self.points)

    @staticmethod
    def padding(latitude, corridor_miles):
        # Conservative geodetic bound; exact distance is checked after projection.
        lat_delta = corridor_miles / 68.0
        max_latitude = min(89.99, abs(latitude) + lat_delta)
        return lat_delta / max(0.0001, math.cos(math.radians(max_latitude))), lat_delta

    def project(self, longitude, latitude, corridor_miles):
        longitude += 360 * round((self.longitude_reference - longitude) / 360)
        point = (longitude, latitude)
        lon_pad, lat_pad = self.padding(latitude, corridor_miles + 0.01)
        indexes = self.tree.query(
            box(longitude - lon_pad, latitude - lat_pad, longitude + lon_pad, latitude + lat_pad)
        )
        best = None
        for index in indexes:
            index = int(index)
            a, b = self.points[index : index + 2]
            central = _angle(a, b)
            delta = _angle(a, point)
            angle = _bearing(a, point) - _bearing(a, b)
            along = math.atan2(math.sin(delta) * math.cos(angle), math.cos(delta))
            fraction = min(1.0, max(0.0, along / central)) if central else 0
            nearest_lon, nearest_lat, _ = GEOD.fwd(
                *a, self.azimuths[index], fraction * self.lengths[index] * METERS_PER_MILE
            )
            perpendicular = distance_miles(point, (nearest_lon, nearest_lat))
            offset = (self.cumulative_miles[index] + fraction * self.lengths[index]) * self.scale
            candidate = Projection(offset, perpendicular, nearest_lon, nearest_lat)
            if best is None or (perpendicular, offset) < (
                best.distance_from_route_miles,
                best.route_offset_miles,
            ):
                best = candidate
        return best if best and best.distance_from_route_miles <= corridor_miles + 1e-7 else None

    def database_boxes(self, corridor_miles):
        """At most 80 overlapping chunk boxes, with dateline splitting."""
        stride = max(1, math.ceil((len(self.points) - 1) / 80))
        bounds = []
        for start in range(0, len(self.points) - 1, stride):
            chunk = self.points[start : start + stride + 1]
            min_lon, max_lon = min(p[0] for p in chunk), max(p[0] for p in chunk)
            min_lat, max_lat = min(p[1] for p in chunk), max(p[1] for p in chunk)
            dx, dy = self.padding(max(abs(min_lat), abs(max_lat)), corridor_miles + 0.01)
            lo, hi = min_lon - dx, max_lon + dx
            # Clip unwrapped intervals onto [-180,180].
            for shift in (-720, -360, 0, 360, 720):
                left, right = max(-180, lo + shift), min(180, hi + shift)
                if left <= right:
                    bounds.append((left, min_lat - dy, right, max_lat + dy))
        return bounds

import math
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.models import CachedRoute

from .cache import cache_key, request_lock
from .http import get_json

METERS_PER_MILE = 1609.344


def validate_route(payload):
    if not isinstance(payload, dict):
        raise PlanningError("osrm_invalid_response", "OSRM returned an invalid response.", 502)
    if payload.get("code") == "NoRoute":
        raise PlanningError("no_route", "No driving route connects these endpoints.", 404)
    if payload.get("code") != "Ok":
        raise PlanningError("osrm_invalid_response", "OSRM could not calculate this route.", 502)
    try:
        route = payload["routes"][0]
        distance, duration = float(route["distance"]), float(route["duration"])
        geometry = route["geometry"]
        coordinates = geometry["coordinates"]
        valid = (
            geometry["type"] == "LineString"
            and len(coordinates) >= 2
            and 0 < distance <= 40_000_000
            and 0 <= duration < 10_000_000
            and math.isfinite(distance)
            and math.isfinite(duration)
        )
        for point in coordinates:
            valid = valid and (
                isinstance(point, list)
                and len(point) == 2
                and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in point
                )
                and -180 <= point[0] <= 180
                and -90 <= point[1] <= 90
            )
        if not valid:
            raise ValueError("Invalid route geometry")
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise PlanningError(
            "osrm_invalid_response", "OSRM returned invalid route geometry or distance.", 502
        ) from exc
    return {
        "distance_miles": distance / METERS_PER_MILE,
        "duration_minutes": duration / 60,
        "geometry": geometry,
    }


def get_route(origin, destination):
    coordinates = [
        [round(point["longitude"], 6), round(point["latitude"], 6)] for point in (origin, destination)
    ]
    key = cache_key([coordinates, settings.OSRM_BASE_URL, "driving-geojson-v1"])
    with request_lock(f"route-{key}"):
        cached = CachedRoute.objects.filter(key=key, expires_at__gt=timezone.now()).first()
        if cached:
            return cached.payload, True
        points = ";".join(f"{longitude:.6f},{latitude:.6f}" for longitude, latitude in coordinates)
        url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{quote(points, safe=',;.-')}"
        route = validate_route(
            get_json(
                url, provider="osrm", params={"overview": "full", "geometries": "geojson", "steps": "false"}
            )
        )
        CachedRoute.objects.update_or_create(
            key=key,
            defaults={
                "payload": route,
                "expires_at": timezone.now() + timedelta(seconds=settings.ROUTE_CACHE_SECONDS),
            },
        )
        return route, False

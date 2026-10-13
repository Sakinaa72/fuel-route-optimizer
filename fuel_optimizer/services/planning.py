from django.conf import settings

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.models import FuelStation

from .cost_calculation import rounded, summarize
from .geocoding import resolve_location
from .optimization import optimize
from .route_geometry import RouteGeometry
from .routing import get_route
from .station_matching import find_candidates


def plan_route(data):
    if not FuelStation.objects.exists():
        raise PlanningError(
            "fuel_data_missing", "Import the supplied fuel-price CSV before planning routes.", 503
        )
    if not FuelStation.objects.filter(latitude__isnull=False, longitude__isnull=False).exists():
        raise PlanningError(
            "station_coordinates_missing",
            "No station coordinates have been resolved. Prepare locations and reimport the CSV.",
            503,
        )
    origin = resolve_location(data["start"])
    destination = resolve_location(data["finish"])
    if (origin["latitude"], origin["longitude"]) == (destination["latitude"], destination["longitude"]):
        raise PlanningError("identical_endpoints", "Start and finish must be different locations.", 400)
    route, cache_hit = get_route(origin, destination)
    geometry = RouteGeometry(route["geometry"]["coordinates"], route["distance_miles"])
    candidates = find_candidates(geometry, data["max_station_detour_miles"], origin)
    plan = optimize(
        route["distance_miles"],
        candidates,
        data["max_range_miles"],
        data["miles_per_gallon"],
        settings.DEPARTURE_PRICE_RADIUS_MILES,
    )
    summary, stops = summarize(plan, route["distance_miles"], data["miles_per_gallon"])
    return {
        "route": {
            "origin": origin,
            "destination": destination,
            "distance_miles": rounded(route["distance_miles"], 4),
            "duration_minutes": rounded(route["duration_minutes"], 2),
            "geometry": route["geometry"],
        },
        "vehicle": {
            "max_range_miles": data["max_range_miles"],
            "miles_per_gallon": data["miles_per_gallon"],
            "derived_tank_capacity_gallons": rounded(data["max_range_miles"] / data["miles_per_gallon"], 4),
        },
        "fuel_summary": summary,
        "fuel_stops": stops,
        "optimization": {
            "objective": "minimize_estimated_fuel_cost",
            "method": "DAG dynamic programming",
            "all_legs_within_max_range": all(
                leg.distance <= data["max_range_miles"] + 1e-8 for leg in plan.legs
            ),
            "candidates_evaluated": len(candidates),
            "route_cache_hit": cache_hit,
            "max_station_detour_miles": data["max_station_detour_miles"],
            "distance_model": "OSRM route offsets; road detours excluded",
            "assumptions": [
                "Departure fuel is available and valued at the cheapest imported price within the departure radius.",
                "Each outgoing leg uses its source price; purchases and tank mixing are not simulated.",
                "Station centroids and perpendicular corridor distances are approximations; verify pump access and actual range.",
            ],
        },
        "attribution": {
            "routing": "OSRM / OpenStreetMap",
            "map_data": "© OpenStreetMap contributors",
            "station_locations": "US Census Bureau 2025 Gazetteer place internal points",
        },
    }

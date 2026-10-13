import math
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.models import CachedGeocoding, CityCoordinate

from .cache import cache_key, request_lock
from .http import get_json
from .locations import city_state_address, ensure_us, normalize_address


def resolve_location(location):
    if isinstance(location, dict):
        ensure_us(location["latitude"], location["longitude"])
        return {"address": "Coordinates", **location, "coordinate_source": "user_coordinates"}
    city_state = city_state_address(location)
    if city_state:
        places = list(CityCoordinate.objects.filter(normalized_city=city_state[0], state=city_state[1])[:2])
        if len(places) == 1:
            place = places[0]
            return {
                "address": location,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "coordinate_source": "census_place_reference",
            }
    key = cache_key([normalize_address(location), settings.GEOCODING_BASE_URL, "geocode-v1"])
    with request_lock(f"geocode-{key}"):
        cached = CachedGeocoding.objects.filter(key=key, expires_at__gt=timezone.now()).first()
        if cached:
            return {**cached.payload, "address": location}
        if not settings.GEOCODING_ENABLED or not settings.GEOCODING_USER_AGENT.strip():
            raise PlanningError(
                "location_not_resolved",
                "No unique local city match. Use US coordinates, or enable geocoding with an identifying User-Agent.",
                400,
            )
        # Serialize all public requests across threads/workers on this one host.
        with request_lock("nominatim-global"):
            slot = settings.VAR_DIR / "nominatim-last-request.txt"
            previous = float(slot.read_text()) if slot.exists() else 0.0
            time.sleep(max(0.0, 1.1 - (time.time() - previous)))
            try:
                result = get_json(
                    f"{settings.GEOCODING_BASE_URL}/search",
                    provider="geocoding",
                    params={
                        "q": location,
                        "format": "jsonv2",
                        "limit": 1,
                        "addressdetails": 1,
                        "countrycodes": "us",
                    },
                    headers={"User-Agent": settings.GEOCODING_USER_AGENT},
                )
            finally:
                slot.write_text(str(time.time()))
        if not isinstance(result, list):
            raise PlanningError("geocoding_invalid_response", "Geocoder returned an invalid response.", 502)
        if not result:
            raise PlanningError("location_not_found", "No US location matched this address.", 404)
        try:
            match = result[0]
            if match["address"]["country_code"].lower() != "us":
                raise PlanningError("non_us_location", "Endpoints must be in the United States.", 400)
            latitude, longitude = float(match["lat"]), float(match["lon"])
            if not (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                raise ValueError("Invalid coordinates")
            ensure_us(latitude, longitude)
            payload = {
                "address": location,
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_source": "nominatim",
                "attribution": "© OpenStreetMap contributors",
            }
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise PlanningError(
                "geocoding_invalid_response", "Geocoder returned invalid coordinates.", 502
            ) from exc
        CachedGeocoding.objects.update_or_create(
            key=key,
            defaults={
                "payload": payload,
                "expires_at": timezone.now() + timedelta(days=settings.GEOCODING_CACHE_DAYS),
            },
        )
        return payload

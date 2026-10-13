import json
import re
import unicodedata
from functools import lru_cache

from django.conf import settings
from shapely.geometry import Point, shape

from fuel_optimizer.errors import PlanningError

from .states import STATE_CODES, STATE_NAMES

STATES = dict(zip((name.casefold() for name in STATE_NAMES), STATE_CODES, strict=True))


def normalize_city(value):
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    tokens = text.split()
    aliases = {"st": "saint", "ft": "fort", "mt": "mount"}
    return " ".join(aliases.get(token, token) for token in tokens)


def normalize_place_city(value):
    # Strip Census legal descriptors only from Census names. "Kansas City" and
    # "Oklahoma City" are actual station/city names and must retain "City".
    text = re.sub(r"\s+\(balance\)$", "", value.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s+(city|town|village|borough|municipality|cdp)$", "", text, flags=re.IGNORECASE)
    return normalize_city(text)


def normalize_address(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_state(value):
    value = value.strip()
    return value.upper() if value.upper() in STATE_CODES else STATES.get(value.casefold())


def city_state_address(address):
    parts = [part.strip() for part in address.split(",")]
    if len(parts) == 3 and parts[-1].casefold() in ("usa", "us", "united states"):
        parts.pop()
    if len(parts) == 2:
        state = normalize_state(parts[1])
        if state:
            return normalize_city(parts[0]), state
    return None


@lru_cache(maxsize=4)
def _boundaries(path, modified):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    return [shape(feature["geometry"]) for feature in data["features"]]


def ensure_us(latitude, longitude):
    path = settings.GEOGRAPHIC_DIR / "us-states.geojson"
    if not path.exists():
        raise PlanningError("geographic_data_missing", "Run prepare_locations before planning routes.", 503)
    if not any(
        polygon.covers(Point(longitude, latitude))
        for polygon in _boundaries(str(path), path.stat().st_mtime_ns)
    ):
        raise PlanningError("non_us_location", "Endpoints must be within the 50 US states or DC.", 400)

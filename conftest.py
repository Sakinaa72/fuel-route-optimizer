import json
from decimal import Decimal

import httpx
import pytest
from rest_framework.test import APIClient

from fuel_optimizer.models import CityCoordinate, FuelStation


@pytest.fixture(autouse=True)
def isolated_settings(settings, tmp_path, monkeypatch):
    settings.VAR_DIR = tmp_path / "var"
    settings.VAR_DIR.mkdir()
    settings.GEOGRAPHIC_DIR = tmp_path / "geographic"
    settings.GEOGRAPHIC_DIR.mkdir()
    # Synthetic polygon ONLY for isolated tests. The application uses Census boundaries.
    polygon = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-125, 24], [-66, 24], [-66, 49], [-125, 49], [-125, 24]]],
                },
            }
        ],
    }
    (settings.GEOGRAPHIC_DIR / "us-states.geojson").write_text(json.dumps(polygon))
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    settings.GEOCODING_ENABLED = False
    settings.ENABLE_FAILURE_DEMO = False

    # No automated test may accidentally reach the live Internet.
    def forbidden(*args, **kwargs):
        raise AssertionError("Live HTTP calls are forbidden in the automated test suite")

    monkeypatch.setattr(httpx.Client, "get", forbidden)
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def places(db):
    return CityCoordinate.objects.bulk_create(
        [
            CityCoordinate(
                geoid="4805000",
                city="Austin city",
                normalized_city="austin",
                state="TX",
                latitude=30.2672,
                longitude=-97.7431,
            ),
            CityCoordinate(
                geoid="4819000",
                city="Dallas city",
                normalized_city="dallas",
                state="TX",
                latitude=32.7767,
                longitude=-96.7970,
            ),
        ]
    )


@pytest.fixture
def station_factory(db):
    def make(index=1, price="3.5000", latitude=30.2672, longitude=-97.7431, **kwargs):
        defaults = {
            "record_key": f"test-{index}",
            "source_truckstop_id": str(index),
            "name": f"Test station {index}",
            "address": "Synthetic test address",
            "city": "Austin",
            "normalized_city": "austin",
            "state": "TX",
            "retail_price": Decimal(price),
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_source": "city_centroid_approximation",
            "coordinate_reference": "test_fixture",
        }
        defaults.update(kwargs)
        return FuelStation.objects.create(**defaults)

    return make


@pytest.fixture
def route_payload():
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 195.4 * 1609.344,
                "duration": 10500,
                "geometry": {"type": "LineString", "coordinates": [[-97.7431, 30.2672], [-96.7970, 32.7767]]},
            }
        ],
    }

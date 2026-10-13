from unittest.mock import Mock

import pytest
from django.utils import timezone

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.models import CachedGeocoding
from fuel_optimizer.services.geocoding import resolve_location

pytestmark = pytest.mark.django_db


@pytest.fixture
def enabled_geocoder(settings):
    settings.GEOCODING_ENABLED = True
    settings.GEOCODING_USER_AGENT = "AssessmentTests/1.0 (offline test fixture)"


def test_normalized_cache_and_global_rate_limit(enabled_geocoder, monkeypatch):
    result = [{"lat": "30.2672", "lon": "-97.7431", "address": {"country_code": "us"}}]
    mock_get, mock_sleep = Mock(return_value=result), Mock()
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", mock_get)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.time.sleep", mock_sleep)
    first = resolve_location("123 Test Rd, Austin, TX")
    assert resolve_location("  123  TEST Rd, Austin, TX  ")["latitude"] == first["latitude"]
    assert mock_get.call_count == 1 and mock_sleep.call_count == 1
    resolve_location("456 Test Rd, Austin, TX")
    assert mock_get.call_count == 2 and mock_sleep.call_args.args[0] > 0.9
    assert mock_get.call_args.kwargs["headers"]["User-Agent"]
    assert mock_get.call_args.kwargs["params"]["countrycodes"] == "us"


@pytest.mark.parametrize(
    "result,code,status",
    [
        ([], "location_not_found", 404),
        ({}, "geocoding_invalid_response", 502),
        ([{}], "geocoding_invalid_response", 502),
        ([{"lat": "51", "lon": "-0.1", "address": {"country_code": "gb"}}], "non_us_location", 400),
        (
            [{"lat": "NaN", "lon": "-97", "address": {"country_code": "us"}}],
            "geocoding_invalid_response",
            502,
        ),
        ([{"lat": "91", "lon": "-97", "address": {"country_code": "us"}}], "geocoding_invalid_response", 502),
    ],
)
def test_provider_failures(enabled_geocoder, monkeypatch, result, code, status):
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", Mock(return_value=result))
    with pytest.raises(PlanningError) as error:
        resolve_location("123 Test Rd, Austin, TX")
    assert error.value.error_code == code and error.value.status_code == status
    assert CachedGeocoding.objects.count() == 0


def test_expired_cache_refresh(enabled_geocoder, monkeypatch):
    mock_get = Mock(return_value=[{"lat": "30.2672", "lon": "-97.7431", "address": {"country_code": "us"}}])
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", mock_get)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.time.sleep", Mock())
    resolve_location("123 Test Rd, Austin, TX")
    CachedGeocoding.objects.update(expires_at=timezone.now())
    resolve_location("123 Test Rd, Austin, TX")
    assert mock_get.call_count == 2


def test_address_based_plan_limits_calls(
    api_client, station_factory, enabled_geocoder, route_payload, monkeypatch
):
    station_factory()
    geocode = Mock(
        side_effect=[
            [{"lat": "30.2672", "lon": "-97.7431", "address": {"country_code": "us"}}],
            [{"lat": "32.7767", "lon": "-96.7970", "address": {"country_code": "us"}}],
        ]
    )
    route = Mock(return_value=route_payload)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", geocode)
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", route)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.time.sleep", Mock())
    body = {"start": "123 Test Rd, Austin, TX", "finish": "456 Test Rd, Dallas, TX"}
    assert api_client.post("/api/v1/route/plan/", body, format="json").status_code == 200
    assert geocode.call_count == 2 and route.call_count == 1
    assert api_client.post("/api/v1/route/plan/", body, format="json").status_code == 200
    assert geocode.call_count == 2 and route.call_count == 1


def test_geocoding_error_is_stable_at_api(api_client, station_factory, enabled_geocoder, monkeypatch):
    station_factory()
    monkeypatch.setattr(
        "fuel_optimizer.services.geocoding.get_json",
        Mock(side_effect=PlanningError("geocoding_timeout", "Timed out", 503)),
    )
    response = api_client.post(
        "/api/v1/route/plan/", {"start": "123 Test Rd, Austin, TX", "finish": "Dallas, TX"}, format="json"
    )
    assert response.status_code == 503 and response.json()["error"]["code"] == "geocoding_timeout"

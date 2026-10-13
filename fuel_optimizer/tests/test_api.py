from unittest.mock import Mock

import httpx
import pytest
from django.utils import timezone

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.models import CachedRoute
from fuel_optimizer.services.http import get_json
from fuel_optimizer.services.routing import validate_route

pytestmark = pytest.mark.django_db
URL = "/api/v1/route/plan/"
BODY = {"start": "Austin, TX", "finish": "Dallas, TX"}


def test_city_success_uses_local_coordinates_one_route_call(
    api_client, places, station_factory, route_payload, monkeypatch
):
    station_factory()
    route_mock = Mock(return_value=route_payload)
    geocode_mock = Mock(side_effect=AssertionError("Local cities must not be geocoded"))
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", route_mock)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", geocode_mock)
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["route"]["geometry"]["coordinates"][0] == [-97.7431, 30.2672]
    assert data["route"]["distance_miles"] == 195.4
    assert data["route"]["duration_minutes"] == 175
    assert data["vehicle"]["derived_tank_capacity_gallons"] == 50
    assert data["fuel_summary"]["estimated_total_fuel_cost_usd"] == 68.39
    assert data["fuel_summary"]["total_fuel_consumed_gallons"] == 19.54
    assert data["fuel_stops"] == []
    assert response["Content-Type"] == "application/json"
    assert route_mock.call_count == 1 and geocode_mock.call_count == 0
    assert "steps" in route_mock.call_args.kwargs["params"]
    assert data["optimization"]["all_legs_within_max_range"]


def test_coordinates_success_and_repeat_cache(api_client, station_factory, route_payload, monkeypatch):
    station_factory()
    route_mock = Mock(return_value=route_payload)
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", route_mock)
    body = {
        "start": {"latitude": 30.2672, "longitude": -97.7431},
        "finish": {"latitude": 32.7767, "longitude": -96.7970},
    }
    assert api_client.post(URL, body, format="json").status_code == 200
    second = api_client.post(URL, {**body, "miles_per_gallon": 20}, format="json")
    assert second.status_code == 200 and second.json()["optimization"]["route_cache_hit"]
    assert second.json()["fuel_summary"]["total_fuel_consumed_gallons"] == 9.77
    assert route_mock.call_count == 1  # vehicle inputs don't change the route geometry


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"start": "Austin, TX"},
        {"finish": "Dallas, TX"},
        {"start": "", "finish": "Dallas, TX"},
        {"start": "12", "finish": "Dallas, TX"},
        {"start": "A" * 301, "finish": "Dallas, TX"},
        {**BODY, "extra": 123},
        {**BODY, "max_range_miles": 0},
        {**BODY, "miles_per_gallon": -1},
        {**BODY, "max_station_detour_miles": 51},
        {**BODY, "max_range_miles": True},
        {**BODY, "miles_per_gallon": "NaN"},
        {**BODY, "miles_per_gallon": "Infinity"},
        {"start": {"latitude": 91, "longitude": -97}, "finish": "Dallas, TX"},
        {"start": {"latitude": True, "longitude": -97}, "finish": "Dallas, TX"},
        {"start": {"latitude": 35}, "finish": "Dallas, TX"},
        {"start": [], "finish": "Dallas, TX"},
    ],
)
def test_input_validation_has_consistent_error(api_client, body):
    response = api_client.post(URL, body, format="json")
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"code", "message", "details", "request_id"}
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"] == response["X-Request-ID"]


def test_missing_dataset_and_unresolved_station_data(api_client, station_factory):
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 503 and response.json()["error"]["code"] == "fuel_data_missing"
    station_factory(latitude=None, longitude=None, coordinate_source="unresolved")
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 503 and response.json()["error"]["code"] == "station_coordinates_missing"


def test_oversized_json_has_stable_error(api_client):
    response = api_client.post(URL, {"start": "A" * 20000, "finish": "Dallas, TX"}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "request_too_large"


def test_malformed_request_json_and_wrong_method(api_client):
    response = api_client.post(URL, '{"start":', content_type="application/json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "validation_error"
    response = api_client.get(URL)
    assert response.status_code == 405 and response.json()["error"]["code"] == "method_not_allowed"


def test_unknown_location_with_disabled_geocoder(api_client, station_factory):
    station_factory()
    response = api_client.post(URL, {**BODY, "start": "Unknownville, TX"}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "location_not_resolved"


def test_non_us_coordinates_rejected(api_client, station_factory):
    station_factory()
    response = api_client.post(URL, {**BODY, "start": {"latitude": 51.5, "longitude": -0.1}}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "non_us_location"


def test_identical_endpoints_and_missing_geography(api_client, places, station_factory, settings):
    station_factory()
    response = api_client.post(URL, {"start": "Austin, TX", "finish": "Austin, TX"}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "identical_endpoints"
    (settings.GEOGRAPHIC_DIR / "us-states.geojson").unlink()
    response = api_client.post(
        URL, {**BODY, "start": {"latitude": 30.2672, "longitude": -97.7431}}, format="json"
    )
    assert response.status_code == 503 and response.json()["error"]["code"] == "geographic_data_missing"


def test_no_route(api_client, places, station_factory, monkeypatch):
    station_factory()
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", Mock(return_value={"code": "NoRoute"}))
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 404 and response.json()["error"]["code"] == "no_route"


@pytest.mark.parametrize(
    "failure,status,code",
    [
        (httpx.ReadTimeout("timeout"), 503, "osrm_timeout"),
        (httpx.ConnectError("failed"), 502, "osrm_unavailable"),
        (
            httpx.HTTPStatusError(
                "bad", request=httpx.Request("GET", "https://provider.test"), response=httpx.Response(500)
            ),
            502,
            "osrm_http_error",
        ),
    ],
)
def test_real_http_adapter_errors_reach_api(
    api_client, places, station_factory, monkeypatch, failure, status, code
):
    station_factory()
    monkeypatch.setattr(httpx.Client, "get", Mock(side_effect=failure))
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert "Traceback" not in response.content.decode()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"code": "InvalidQuery"},
        {"code": "Ok", "routes": []},
        {
            "code": "Ok",
            "routes": [
                {"distance": -1, "duration": 1, "geometry": {"type": "LineString", "coordinates": []}}
            ],
        },
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 100,
                    "duration": 1,
                    "geometry": {"type": "LineString", "coordinates": [[-100, 35], [999, 36]]},
                }
            ],
        },
    ],
)
def test_malformed_osrm_payload(payload):
    with pytest.raises(PlanningError) as error:
        validate_route(payload)
    assert error.value.status_code == 502


def test_malformed_json_and_explicit_timeouts(monkeypatch, settings):
    response = Mock()
    response.json.side_effect = ValueError("malformed")
    mock_get = Mock(return_value=response)
    monkeypatch.setattr(httpx.Client, "get", mock_get)
    with pytest.raises(PlanningError) as error:
        get_json("https://provider.test", provider="osrm")
    assert error.value.error_code == "osrm_unavailable"
    assert settings.HTTP_CONNECT_TIMEOUT > 0 and settings.HTTP_READ_TIMEOUT > 0


def test_cached_route_expiry_refreshes_once(api_client, places, station_factory, monkeypatch, route_payload):
    station_factory()
    mock_get = Mock(return_value=route_payload)
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", mock_get)
    assert api_client.post(URL, BODY, format="json").status_code == 200
    CachedRoute.objects.update(expires_at=timezone.now())
    assert api_client.post(URL, BODY, format="json").status_code == 200
    assert mock_get.call_count == 2


def test_health_is_local_and_reports_readiness(api_client, places, station_factory):
    assert api_client.get("/api/v1/health/").json()["fuel_dataset_loaded"] is False
    station_factory()
    data = api_client.get("/api/v1/health/").json()
    assert data["ready_to_plan"] and data["stations_total"] == 1


def test_demo_docs_and_schema(api_client):
    assert api_client.get("/demo/").status_code == 200
    assert b"leaflet" in api_client.get("/demo/").content
    assert api_client.get("/docs/").status_code == 200
    schema = api_client.get("/openapi.json").json()
    assert schema["openapi"] == "3.1.0" and "/api/v1/route/plan/" in schema["paths"]


def test_local_failure_demo_is_disabled_by_default_and_opt_in(
    api_client, places, station_factory, route_payload, monkeypatch, settings
):
    station_factory()
    route_mock = Mock(return_value=route_payload)
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", route_mock)
    response = api_client.post(URL, BODY, format="json", HTTP_X_DEMO_UPSTREAM_FAILURE="timeout")
    assert response.status_code == 200
    settings.ENABLE_FAILURE_DEMO = True
    response = api_client.post(URL, BODY, format="json", HTTP_X_DEMO_UPSTREAM_FAILURE="timeout")
    assert response.status_code == 503 and "Simulated" in response.json()["error"]["message"]
    assert route_mock.call_count == 1


def test_infeasible_plan_uses_422(api_client, places, station_factory, monkeypatch):
    station_factory()
    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 900 * 1609.344,
                "duration": 50000,
                "geometry": {"type": "LineString", "coordinates": [[-97.7431, 30.2672], [-83.0, 35.0]]},
            }
        ],
    }
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", Mock(return_value=payload))
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 422 and response.json()["error"]["code"] == "no_feasible_refueling_plan"


def test_unexpected_exception_never_exposes_details(api_client, monkeypatch):
    monkeypatch.setattr("fuel_optimizer.views.plan_route", Mock(side_effect=RuntimeError("secret/path")))
    response = api_client.post(URL, BODY, format="json")
    assert response.status_code == 500 and response.json()["error"]["code"] == "internal_error"
    assert "secret/path" not in response.content.decode()

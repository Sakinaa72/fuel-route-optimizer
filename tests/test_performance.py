import random
from decimal import Decimal
from time import perf_counter
from unittest.mock import Mock

import pytest

from fuel_optimizer.models import FuelStation


@pytest.mark.django_db
def test_8151_rows_are_filtered_locally(places, station_factory, route_payload, api_client, monkeypatch):
    station_factory()
    rng = random.Random(8151)
    FuelStation.objects.bulk_create(
        [
            FuelStation(
                record_key=f"perf-{i}",
                source_truckstop_id=str(i),
                name="Synthetic performance fixture",
                address="Fixture",
                city="Fixture",
                normalized_city="fixture",
                state="TX",
                retail_price=Decimal("4.0000"),
                latitude=rng.uniform(25, 48),
                longitude=rng.uniform(-124, -68),
                coordinate_source="city_centroid_approximation",
            )
            for i in range(8150)
        ],
        batch_size=500,
    )
    route = Mock(return_value=route_payload)
    geocode = Mock(side_effect=AssertionError("Station/endpoint geocoding must not occur"))
    monkeypatch.setattr("fuel_optimizer.services.routing.get_json", route)
    monkeypatch.setattr("fuel_optimizer.services.geocoding.get_json", geocode)
    started = perf_counter()
    response = api_client.post(
        "/api/v1/route/plan/", {"start": "Austin, TX", "finish": "Dallas, TX"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["optimization"]["candidates_evaluated"] < 200
    assert route.call_count == 1 and geocode.call_count == 0
    # Broad guard against algorithmic regressions, not a claimed production SLA.
    assert perf_counter() - started < 10

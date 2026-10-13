#!/usr/bin/env python
"""Audit a running HTTP deployment against the private CSV and local Census import."""

import argparse
import csv
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402

from fuel_optimizer.models import CityCoordinate  # noqa: E402


def audit(data, source_records):
    route, summary, stops = data["route"], data["fuel_summary"], data["fuel_stops"]
    legs, vehicle = summary["legs"], data["vehicle"]
    geometry = route["geometry"]
    assert geometry["type"] == "LineString" and len(geometry["coordinates"]) >= 2
    assert all(-180 <= lon <= 180 and -90 <= lat <= 90 for lon, lat in geometry["coordinates"])
    assert [stop["sequence"] for stop in stops] == list(range(1, len(stops) + 1))
    offsets = [0, *[stop["route_offset_miles"] for stop in stops], route["distance_miles"]]
    assert all(a < b for a, b in zip(offsets, offsets[1:]))
    assert len(legs) == len(stops) + 1
    assert legs[0]["source_type"] == "departure_inventory"
    assert legs[-1]["end_offset_miles"] == route["distance_miles"]
    details = [summary["departure_price_source"], *stops]
    for index, (leg, detail) in enumerate(zip(legs, details)):
        identity = tuple(detail[key] for key in ("source_truckstop_id", "name", "address", "city", "state"))
        price = Decimal(str(detail["retail_price_usd_per_gallon"]))
        assert (*identity, price) in source_records, "Returned identity/price absent from supplied CSV"
        assert leg["price_source_station_id"] == detail["station_id"]
        assert leg["start_offset_miles"] == offsets[index]
        assert leg["end_offset_miles"] == offsets[index + 1]
        assert 0 < leg["distance_miles"] <= vehicle["max_range_miles"] + 0.0001
        assert abs(leg["distance_miles"] - (offsets[index + 1] - offsets[index])) <= 0.0002
        assert abs(leg["gallons"] - leg["distance_miles"] / vehicle["miles_per_gallon"]) <= 0.0001
        # The HTTP response rounds miles/gallons to four decimals. Allow only that
        # display uncertainty plus half a cent when checking the unrounded formula.
        calculated = Decimal(str(leg["distance_miles"])) / Decimal(str(vehicle["miles_per_gallon"])) * price
        allowance = Decimal("0.005") + Decimal("0.0001") * price / Decimal(str(vehicle["miles_per_gallon"]))
        assert abs(calculated - Decimal(str(leg["cost_usd"]))) <= allowance
        assert Decimal(str(leg["retail_price_usd_per_gallon"])) == price
        place = CityCoordinate.objects.get(geoid=detail["coordinate_reference"].split(":")[-1])
        assert (detail["latitude"], detail["longitude"]) == (place.latitude, place.longitude)
        assert detail["coordinate_source"] == "city_centroid_approximation"
        assert (
            detail["distance_from_route_miles"] <= data["optimization"]["max_station_detour_miles"] + 0.0001
        )
        if index:
            assert detail["estimated_leg_cost_usd"] == leg["cost_usd"]
    cost = sum(Decimal(str(leg["cost_usd"])) for leg in legs)
    assert cost == Decimal(str(summary["estimated_total_fuel_cost_usd"]))
    assert (
        Decimal(str(summary["departure_fuel_value_usd"]))
        + Decimal(str(summary["estimated_en_route_allocated_fuel_cost_usd"]))
        == cost
    )
    assert (
        abs(summary["total_fuel_consumed_gallons"] - route["distance_miles"] / vehicle["miles_per_gallon"])
        <= 0.0001
    )
    return {
        "distance_miles": route["distance_miles"],
        "fuel_gallons": summary["total_fuel_consumed_gallons"],
        "estimated_cost_usd": float(cost),
        "stops": len(stops),
        "max_leg_miles": max(leg["distance_miles"] for leg in legs),
        "geometry_points": len(geometry["coordinates"]),
        "first_route_cache_hit": data["optimization"]["route_cache_hit"],
        "source_prices_and_census_coordinates_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, default=Path("var/http-api-verification.json"))
    args = parser.parse_args()
    with settings.FUEL_PRICES_CSV.open(encoding="utf-8-sig", newline="") as stream:
        records = {
            (
                *[
                    row[key].strip()
                    for key in ("OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State")
                ],
                Decimal(row["Retail Price"]),
            )
            for row in csv.DictReader(stream)
        }
    report = {"base_url": args.base_url}
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90, follow_redirects=True) as client:
        health = client.get("/api/v1/health/")
        health.raise_for_status()
        report["health"] = health.json()
        assert report["health"]["ready_to_plan"]
        assert (
            report["health"]["stations_total"],
            report["health"]["stations_located"],
            report["health"]["stations_unresolved"],
        ) == (8125, 7033, 1092)
        report["pages"] = {}
        for path, expected in (
            ("/demo/", "leaflet"),
            ("/docs/", "swagger-ui"),
            ("/static/fuel_optimizer/swagger-init.js", "SwaggerUIBundle"),
        ):
            page = client.get(path)
            page.raise_for_status()
            assert expected in page.text
            report["pages"][path] = page.status_code
        schema = client.get("/openapi.json")
        schema.raise_for_status()
        assert schema.json()["servers"][0]["url"] == "/"
        report["routes"] = {}
        for name, body in (
            ("short", {"start": "Austin, TX", "finish": "Dallas, TX"}),
            ("long", {"start": "Miami, FL", "finish": "Ellensburg, WA"}),
        ):
            response = client.post("/api/v1/route/plan/", json=body)
            assert response.status_code == 200, response.text
            checked = audit(response.json(), records)
            repeated = client.post("/api/v1/route/plan/", json=body)
            assert repeated.status_code == 200 and repeated.json()["optimization"]["route_cache_hit"]
            audit(repeated.json(), records)
            changed = client.post("/api/v1/route/plan/", json={**body, "miles_per_gallon": 20})
            assert changed.status_code == 200 and changed.json()["optimization"]["route_cache_hit"]
            audit(changed.json(), records)
            assert (
                abs(
                    changed.json()["fuel_summary"]["total_fuel_consumed_gallons"] * 2
                    - response.json()["fuel_summary"]["total_fuel_consumed_gallons"]
                )
                <= 0.0001
            )
            checked.update(request=body, repeat_route_cache_hit=True, changed_mpg_cache_hit=True)
            report["routes"][name] = checked
        invalid = client.post("/api/v1/route/plan/", json={"start": "Austin, TX"})
        assert invalid.status_code == 400 and "error" in invalid.json()
        missing = client.get("/verification-nonexistent-path/")
        assert (
            missing.status_code == 404
            and "Traceback" not in missing.text
            and "DEBUG = True" not in missing.text
        )
        report["invalid_input_status"] = invalid.status_code
        report["non_debug_404_status"] = missing.status_code
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

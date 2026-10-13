#!/usr/bin/env python
"""Opt-in live integration audit against imported prices; normal pytest stays offline."""

import argparse
import csv
import json
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from fuel_optimizer.models import CachedRoute, CityCoordinate, FuelStation  # noqa: E402
from fuel_optimizer.services import geocoding, routing  # noqa: E402
from fuel_optimizer.services.cache import cache_key  # noqa: E402
from fuel_optimizer.services.route_geometry import RouteGeometry  # noqa: E402
from fuel_optimizer.services.station_matching import find_candidates  # noqa: E402


def independent_optimum(distance, candidates, departure_price, mpg, max_range):
    """Separate forward relaxation with Decimal costs, independent of optimizer DP."""
    nodes = [(Decimal(0), Decimal(str(departure_price)))]
    nodes += [(Decimal(str(c.offset)), c.price) for c in candidates if 1e-8 < c.offset < distance - 1e-8]
    nodes.sort(key=lambda node: (node[0], node[1]))
    nodes.append((Decimal(str(distance)), Decimal(0)))
    best = [Decimal("Infinity")] * len(nodes)
    best[0] = Decimal(0)
    for index, (position, price) in enumerate(nodes[:-1]):
        if not best[index].is_finite():
            continue
        for end in range(index + 1, len(nodes)):
            gap = nodes[end][0] - position
            if gap > Decimal(str(max_range)) + Decimal("0.00000001"):
                break
            if gap > 0:
                cost = best[index] + gap / Decimal(str(mpg)) * price
                best[end] = min(best[end], cost)
    return best[-1]


def audit_response(data, source_records):
    route, summary, stops = data["route"], data["fuel_summary"], data["fuel_stops"]
    legs, vehicle = summary["legs"], data["vehicle"]
    assert route["geometry"]["type"] == "LineString" and len(route["geometry"]["coordinates"]) >= 2
    assert [stop["sequence"] for stop in stops] == list(range(1, len(stops) + 1))
    offsets = [stop["route_offset_miles"] for stop in stops]
    assert all(a < b for a, b in zip(offsets, offsets[1:]))
    assert legs[0]["source_type"] == "departure_inventory" and legs[0]["start_offset_miles"] == 0
    assert legs[-1]["end_offset_miles"] == route["distance_miles"]
    assert len(legs) == len(stops) + 1
    assert all(0 < leg["distance_miles"] <= vehicle["max_range_miles"] + 0.0001 for leg in legs)
    assert abs(sum(leg["distance_miles"] for leg in legs) - route["distance_miles"]) <= len(legs) * 0.0001
    assert (
        abs(summary["total_fuel_consumed_gallons"] - route["distance_miles"] / vehicle["miles_per_gallon"])
        <= 0.0001
    )
    total = sum(Decimal(str(leg["cost_usd"])) for leg in legs)
    assert total == Decimal(str(summary["estimated_total_fuel_cost_usd"]))
    assert (
        Decimal(str(summary["departure_fuel_value_usd"]))
        + Decimal(str(summary["estimated_en_route_allocated_fuel_cost_usd"]))
        == total
    )
    for detail in [summary["departure_price_source"], *stops]:
        station = FuelStation.objects.get(pk=detail["station_id"])
        content = (
            station.source_truckstop_id,
            station.name,
            station.address,
            station.city,
            station.state,
            station.rack_id,
            station.retail_price,
        )
        assert content in source_records, "Station/price is absent from the original supplied CSV"
        assert Decimal(str(detail["retail_price_usd_per_gallon"])) == station.retail_price
        for field in ("name", "address", "city", "state", "latitude", "longitude", "coordinate_source"):
            assert detail[field] == getattr(station, field)
        place = CityCoordinate.objects.get(geoid=station.coordinate_reference.split(":")[-1])
        assert (station.latitude, station.longitude) == (place.latitude, place.longitude)
        assert (
            detail["distance_from_route_miles"] <= data["optimization"]["max_station_detour_miles"] + 0.0001
        )
    for index, stop in enumerate(stops, 1):
        assert legs[index]["price_source_station_id"] == stop["station_id"]
        assert legs[index]["start_offset_miles"] == stop["route_offset_miles"]
        assert legs[index]["cost_usd"] == stop["estimated_leg_cost_usd"]
    raw_route, cache_hit = routing.get_route(route["origin"], route["destination"])
    assert cache_hit, "Audit must reuse the existing route, not call a provider for stations"
    geometry = RouteGeometry(route["geometry"]["coordinates"], raw_route["distance_miles"])
    candidates = find_candidates(geometry, data["optimization"]["max_station_detour_miles"], route["origin"])
    sources = [
        c
        for c in candidates
        if c.distance_from_origin <= settings.DEPARTURE_PRICE_RADIUS_MILES
        and c.offset <= settings.DEPARTURE_PRICE_RADIUS_MILES
    ]
    assert Decimal(str(summary["departure_price_source"]["retail_price_usd_per_gallon"])) == min(
        c.price for c in sources
    )
    by_id = {c.station_id: c for c in candidates}
    selected = [0.0] + [by_id[s["station_id"]].offset for s in stops] + [raw_route["distance_miles"]]
    unrounded = Decimal(0)
    for index, leg in enumerate(legs):
        exact_gallons = Decimal(str(selected[index + 1] - selected[index])) / Decimal(
            str(vehicle["miles_per_gallon"])
        )
        exact_cost = exact_gallons * by_id[leg["price_source_station_id"]].price
        assert exact_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal(str(leg["cost_usd"]))
        unrounded += exact_cost
    oracle = independent_optimum(
        raw_route["distance_miles"],
        candidates,
        summary["departure_price_source"]["retail_price_usd_per_gallon"],
        vehicle["miles_per_gallon"],
        vehicle["max_range_miles"],
    )
    assert abs(oracle - unrounded) < Decimal("0.0000001"), (
        "Optimizer disagrees with independent Decimal path relaxation"
    )
    return {
        "distance_miles": route["distance_miles"],
        "fuel_gallons": summary["total_fuel_consumed_gallons"],
        "estimated_cost_usd": float(total),
        "stops": len(stops),
        "candidates": len(candidates),
        "max_leg_miles": max(leg["distance_miles"] for leg in legs),
        "geometry_points": len(route["geometry"]["coordinates"]),
        "independent_optimum_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path("var/demo-examples.json"))
    args = parser.parse_args()
    with settings.FUEL_PRICES_CSV.open(encoding="utf-8-sig", newline="") as stream:
        records = {
            (
                row["OPIS Truckstop ID"].strip(),
                row["Truckstop Name"].strip(),
                row["Address"].strip(),
                row["City"].strip(),
                row["State"].strip(),
                row["Rack ID"].strip(),
                Decimal(row["Retail Price"]),
            )
            for row in csv.DictReader(stream)
        }
    examples = json.loads(args.examples.read_text())
    client, report = Client(), {}
    for kind, example in examples.items():
        body = example["request"]
        endpoints = [geocoding.resolve_location(body[key]) for key in ("start", "finish")]
        coordinates = [[round(point["longitude"], 6), round(point["latitude"], 6)] for point in endpoints]
        key = cache_key([coordinates, settings.OSRM_BASE_URL, "driving-geojson-v1"])
        # Expire only the example route to measure a deliberate cache miss.
        CachedRoute.objects.filter(key=key).update(expires_at=timezone.now())
        with (
            patch("fuel_optimizer.services.routing.get_json", wraps=routing.get_json) as route_calls,
            patch("fuel_optimizer.services.geocoding.get_json", wraps=geocoding.get_json) as geocode_calls,
        ):
            response = client.post(
                "/api/v1/route/plan/", data=json.dumps(body), content_type="application/json"
            )
            assert response.status_code == 200, response.content.decode()
            result = response.json()
            assert route_calls.call_count == 1 and geocode_calls.call_count == 0
            checked = audit_response(result, records)
            repeated = client.post(
                "/api/v1/route/plan/", data=json.dumps(body), content_type="application/json"
            )
            assert repeated.status_code == 200 and repeated.json()["optimization"]["route_cache_hit"]
            assert route_calls.call_count == 1 and geocode_calls.call_count == 0
            # Current vehicle settings must be recalculated while geometry remains cached.
            changed = client.post(
                "/api/v1/route/plan/",
                data=json.dumps({**body, "miles_per_gallon": 20}),
                content_type="application/json",
            )
            assert changed.status_code == 200 and changed.json()["optimization"]["route_cache_hit"]
            assert route_calls.call_count == 1 and geocode_calls.call_count == 0
            assert (
                abs(
                    changed.json()["fuel_summary"]["total_fuel_consumed_gallons"] * 2
                    - result["fuel_summary"]["total_fuel_consumed_gallons"]
                )
                <= 0.0001
            )
            checked.update(
                {
                    "request": body,
                    "first_request_external_calls": {"routing": 1, "geocoding": 0},
                    "repeat_external_calls": {"routing": 0, "geocoding": 0},
                    "changed_mpg_external_calls": {"routing": 0, "geocoding": 0},
                }
            )
            report[kind] = checked
            print(json.dumps({kind: checked}))
    Path("var/live-api-verification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Verify Postman examples against real imported prices and real OSRM responses."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.db.models import Count  # noqa: E402

from fuel_optimizer.errors import PlanningError  # noqa: E402
from fuel_optimizer.models import CityCoordinate, FuelStation  # noqa: E402
from fuel_optimizer.serializers import PlanRequestSerializer  # noqa: E402
from fuel_optimizer.services.planning import plan_route  # noqa: E402
from fuel_optimizer.services.route_geometry import distance_miles  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-attempts", type=int, default=6)
    args = parser.parse_args()
    if not FuelStation.objects.exists():
        parser.exit(
            1,
            "Real price data is missing. Import the supplied CSV first; no example successes were generated.\n",
        )
    groups = (
        FuelStation.objects.filter(latitude__isnull=False, longitude__isnull=False)
        .exclude(state__in=["AK", "HI"])
        .values("state", "normalized_city")
        .annotate(count=Count("id"))
        .order_by("-count", "state", "normalized_city")[:80]
    )
    pool = []
    for group in groups:
        places = list(
            CityCoordinate.objects.filter(state=group["state"], normalized_city=group["normalized_city"])[:2]
        )
        if len(places) == 1:
            place = places[0]
            pool.append(
                (f"{group['normalized_city'].title()}, {place.state}", (place.longitude, place.latitude))
            )
    pairs = []
    for index, start in enumerate(pool):
        for finish in pool[index + 1 :]:
            miles = distance_miles(start[1], finish[1])
            pairs.append((miles, {"start": start[0], "finish": finish[0]}))
    short = [body for miles, body in sorted(pairs, key=lambda pair: pair[0]) if 75 <= miles <= 250]
    long = [body for miles, body in sorted(pairs, key=lambda pair: -pair[0]) if miles >= 1100]
    options = {
        "short": [{"start": "Austin, TX", "finish": "Dallas, TX"}, *short],
        "long": [{"start": "Miami, FL", "finish": "Ellensburg, WA"}, *long],
    }
    verified = {}
    for kind, bodies in options.items():
        for body in bodies[: max(1, min(args.max_attempts, 10))]:
            serializer = PlanRequestSerializer(data=body)
            serializer.is_valid(raise_exception=True)
            try:
                result = plan_route(serializer.validated_data)
                if kind == "long" and len(result["fuel_stops"]) < 2:
                    print(f"{kind}: route is feasible but has fewer than two stops; trying another pair.")
                    continue
                verified[kind] = {"request": body, "response": result}
                print(
                    f"{kind}: {body['start']} → {body['finish']}; {result['route']['distance_miles']:.1f} mi; {len(result['fuel_stops'])} stops; ${result['fuel_summary']['estimated_total_fuel_cost_usd']:.2f}"
                )
                break
            except PlanningError as error:
                print(f"{kind}: {body['start']} → {body['finish']}: {error.error_code}")
            finally:
                time.sleep(1.1)
    if len(verified) != 2:
        parser.exit(
            1,
            "Could not verify both examples. Check import coverage and provider availability. No success environment was generated.\n",
        )
    values = [{"key": "base_url", "value": "http://127.0.0.1:8000", "enabled": True}]
    for kind in ("short", "long"):
        for endpoint in ("start", "finish"):
            values.append(
                {"key": f"{kind}_{endpoint}", "value": verified[kind]["request"][endpoint], "enabled": True}
            )
    output = Path("var")
    output.mkdir(exist_ok=True)
    (output / "postman-verified.postman_environment.json").write_text(
        json.dumps({"name": "Fuelway verified real-data examples", "values": values}, indent=2) + "\n"
    )
    (output / "demo-examples.json").write_text(json.dumps(verified, indent=2) + "\n")
    print(
        "Import var/postman-verified.postman_environment.json into Postman. Actual responses are saved in var/demo-examples.json."
    )


if __name__ == "__main__":
    main()

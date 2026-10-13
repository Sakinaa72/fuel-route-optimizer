from decimal import ROUND_HALF_UP, Decimal


def rounded(value, digits=2):
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def leg_cost(distance, mpg, price):
    return (Decimal(str(distance)) / Decimal(str(mpg)) * price).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def render_station(candidate):
    row = candidate.station
    return {
        "station_id": candidate.station_id,
        "source_truckstop_id": row["source_truckstop_id"],
        "name": row["name"],
        "address": row["address"],
        "city": row["city"],
        "state": row["state"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "coordinate_source": row["coordinate_source"],
        "coordinate_reference": row["coordinate_reference"],
        "retail_price_usd_per_gallon": float(candidate.price),
        "route_offset_miles": rounded(candidate.offset, 4),
        "distance_from_route_miles": rounded(candidate.distance_from_route, 4),
    }


def summarize(plan, distance, mpg):
    legs, stops = [], []
    total = Decimal("0")
    for index, leg in enumerate(plan.legs):
        cost = leg_cost(leg.distance, mpg, leg.source.price)
        total += cost
        detail = {
            "sequence": index + 1,
            "source_type": "departure_inventory" if index == 0 else "fuel_stop",
            "price_source_station_id": leg.source.station_id,
            "start_offset_miles": rounded(leg.start_offset, 4),
            "end_offset_miles": rounded(leg.end_offset, 4),
            "distance_miles": rounded(leg.distance, 4),
            "gallons": rounded(leg.distance / mpg, 4),
            "retail_price_usd_per_gallon": float(leg.source.price),
            "cost_usd": float(cost),
        }
        legs.append(detail)
        if index:
            stops.append(
                {
                    "sequence": index,
                    **render_station(leg.source),
                    "estimated_leg_distance_miles": detail["distance_miles"],
                    "estimated_leg_gallons": detail["gallons"],
                    "estimated_leg_cost_usd": detail["cost_usd"],
                    "reason_selected": "Minimum estimated outgoing-segment cost with feasible route gaps",
                }
            )
    return {
        "total_fuel_consumed_gallons": rounded(distance / mpg, 4),
        "estimated_total_fuel_cost_usd": float(total),
        "estimated_cost_per_mile_usd": rounded(total / Decimal(str(distance)), 4),
        "departure_fuel_value_usd": legs[0]["cost_usd"],
        "estimated_en_route_allocated_fuel_cost_usd": float(total - Decimal(str(legs[0]["cost_usd"]))),
        "cost_model": "outgoing_segment_price_with_departure_inventory_proxy",
        "currency": "USD",
        "volume_unit": "US gallons",
        "departure_price_source": render_station(plan.departure_source),
        "legs": legs,
    }, stops
